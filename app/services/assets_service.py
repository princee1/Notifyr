import json
from random import randint
import traceback
from minio.datatypes import Object
from fastapi import HTTPException,status
from app.classes.auth_permission import AssetsPermission, AuthPermission
from app.definition._error import BaseError
from app.interface.timers import IntervalParams, SchedulerInterface
from app.services.aws_service import AmazonS3Service
import app.services.aws_service as aws_service
from app.services.database_service import RedisService
from app.services.secret_service import HCVaultService
from app.services.setting_service import SettingService
from app.utils.constant import MinioConstant, RedisConstant
from app.utils.prettyprint import printJSON
from app.utils.tools import RunInThreadPool
from .config_service import AssetMode, CeleryMode, ConfigService, UvicornWorkerService
from app.utils.fileIO import FDFlag, JSONFile
from app.classes.template import Asset, Extension, HTMLTemplate, MLTemplate, PDFTemplate, SMSTemplate, PhoneTemplate, SkipTemplateCreationError, Template
from .file_service import FileService, FTPService
from app.definition import _service
from enum import Enum
import os
from threading import Thread
from typing import Any, Callable, Literal, Dict, get_args
from app.utils.helper import IntegrityCache, PointerIterator, flatten_dict, issubclass_of
from app.utils.globals import ASSET_SEPARATOR, DIRECTORY_SEPARATOR


class AssetNotFoundError(BaseError):
    ...

class AssetTypeNotFoundError(BaseError):
    ...

class AssetTypeNotAllowedError(BaseError):
    ...

class AssetType(Enum):
    IMAGES = "images"
    PDF = "pdf"
    SMS = "sms"
    PHONE = "phone"
    EMAIL = "email"
    
RouteAssetType = Literal['email', 'sms', 'phone']


class AssetConfusionError(BaseError):
    asset_confusion = (AssetType.PHONE.value,AssetType.SMS.value)

    def __init__(self,filename,*args):
        super().__init__(*args)
        self.filename = filename

        

EXTENSION_TO_ASSET_TYPE:dict[str,AssetType|str] = {
    Extension.JPEG.value: AssetType.IMAGES.value,
    Extension.PDF.value: AssetType.PDF.value,
    Extension.SCSS.value: AssetType.EMAIL.value,
    Extension.CSS.value: AssetType.EMAIL.value,
    Extension.HTML.value: AssetType.EMAIL.value,
    Extension.XML.value: [AssetType.PHONE.value, AssetType.SMS.value]
}


def extension(extension: Extension): return f".{extension.value}"

#############################################                ##################################################
#                                               READER                                                        #  
#############################################                ##################################################


class Reader:
    def __init__(self, configService: ConfigService,fileService:FileService,asset_cache:IntegrityCache, asset: type[Asset] = Asset, additionalCode: Callable = None) -> None:
        self.asset = asset
        self.configService = configService
        self.func = additionalCode
        self.fileService = fileService
        self.values: Dict[str, Asset] = {}
        self.asset_cache = asset_cache

    
    def __call__(self, ext: Extension, flag: FDFlag, rootParam: str = None, encoding="utf-8") -> dict[str, Asset]:
        """
        :param ext:
        :type ext: Extension

        :param flag:
        :type flag: FDFlag

        :param rootFlag: 

        :param encoding:
        """
        self.safeReader(ext,flag,rootParam,encoding)
        return self.values
    
    def create_assets(self, relpath, content, dir, keyName,size=0):
        try:
            self.values[relpath] = self.asset(keyName, content, dir,size)
        except SkipTemplateCreationError as e:
            print(e.args[0])
                #printJSON(e.args[1])
        except Exception as e :
            print(e.__class__,e)

        if issubclass_of(Template, self.asset):
            if self.func != None:
                self.func(self.values[relpath])
    
    def path(self,val,root=True):
        return f"{self.configService.OBJECTS_DIR if root else ''}{self.configService.ASSETS_DIR}{val}"

    
    def safeReader(self, ext: Extension, flag: FDFlag, rootFlag: bool | str = True, encoding="utf-8"):
        try:
            self.read(ext, flag, rootFlag, encoding)
        except OSError as e:
            pass
        except TypeError as e:
            pass
        except AttributeError as e:
            pass
    
    def read(self, ext: Extension, flag: FDFlag, rootParam: str = None, encoding="utf-8"):
        """
        This function reads files with a specific extension, processes them, and stores the content in a
        dictionary.

        :param ext: It is used to specify the file extension that you want to read
        :type ext: Extension
        :param flag:It is likely used to control how the file is opened and read, such as specifying whether the file should be opened in read mode, write mode, or both.
        :type flag: FDFlag
        :param rootFlag: The `rootFlag` parameter in the `read` method is a boolean flag that determines
        whether the root directory should be considered when reading files.
        :param encoding: The `encoding` parameter in the `read` method specifies the character encoding
        to be used when reading the files. In this case, the default encoding is set to "utf-8"
        """

class DiskReader(Reader):

    def __init__(self,configService:ConfigService, fileService: FileService,asset_cache:IntegrityCache, asset: type[Asset] = Asset, additionalCode: Callable = None) -> None:
        super().__init__(configService,fileService,asset_cache, asset, additionalCode)
        self.asset = asset
        self.func = additionalCode
        self.fileService = fileService
        self.configService = configService

    def read(self, ext: Extension, flag: FDFlag, rootParam: str = None, encoding="utf-8"):
        extension_ = extension(ext)
        root = self.path(rootParam) if type(rootParam) is str  else self.path(ext.value)
        setTempFile: set[str] = set()
        for file in self.fileService.listFileExtensions(extension_, root, recursive=True):
            relpath = root + os.path.sep+file

            info = str(self.fileService.get_file_info(relpath))
            if self.asset_cache.cache(relpath,info):
                continue

            filename, content, dir = self.fileService.readFileDetail(relpath, flag, encoding)
            keyName = filename if not setTempFile else file
            setTempFile.add(keyName)
            self.create_assets(relpath, content, dir, keyName)

class ThreadedReader(DiskReader):
    def __init__(self,configService:ConfigService, fileService: FileService,asset_cache:IntegrityCache, asset: Asset = Asset, additionalCode: Callable[..., Any] = None) -> None:
        super().__init__(configService,fileService,asset_cache,asset, additionalCode)
        self.thread: Thread

    def read(self, ext: Extension, flag: FDFlag, rootFlag: bool | str = True, encoding="utf-8"):
        self.thread = Thread(target=super().read, args=(ext, flag, rootFlag, encoding))
        self.thread.start()

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        self.safeReader(*args)
        return self

    def join(self) -> dict[str, Asset]:
        self.thread.join()
        return self.values

class S3ObjectReader(Reader):   

    def __init__(self, configService: ConfigService, awsService: AmazonS3Service,vaultService:HCVaultService,objects:list[Object],asset_cache:IntegrityCache,fileService:FileService, asset: type[Asset] = Asset, additionalCode: Callable = None) -> None:
        super().__init__(configService,fileService,asset_cache, asset, additionalCode)
        self.awsService = awsService
        self.vaultService = vaultService
        self.objects:list[Object] =objects
    
    def read(self, ext: Extension, flag: FDFlag, rootParam: str = None, encoding="utf-8"):
        ext= f".{ext.value}"
        # objects = self.awsService.list_objects(rootParam,True,match=ext)
        for obj in self.objects:
            if not (not obj.is_delete_marker and obj.is_latest=='true'):
                continue
            
            if not self.fileService.soft_is_file(obj.object_name):
                continue

            encrypted = obj.metadata.get(MinioConstant.ENCRYPTED_KEY,False) if obj.metadata else False

            if self.fileService.simple_file_matching(obj.object_name,rootParam,ext) and not self.asset_cache.cache(obj.object_name,obj.etag):

                obj_content = self.awsService.read_object(object_name=obj.object_name)
                obj_content = obj_content.read()
                if encrypted:
                    obj_content = self.vaultService.transit_engine.decrypt(obj_content.decode(),'s3-rest-key')
                    if flag == FDFlag.READ_BYTES:
                        obj_content = obj_content.encode()
                
                if flag != FDFlag.READ_BYTES:
                    obj_content = obj_content.decode(encoding)
                obj_dir = self.fileService.get_file_dir(obj.object_name,'pure')
                self.create_assets(obj.object_name,obj_content,obj_dir,self.configService.normalize_assets_path(obj.object_name,'add'),obj.size)
    

#############################################                ##################################################
#                                              ASSET SERVICE                                                  #
#############################################                ##################################################

@_service.Service(
    links=[_service.LinkDep(AmazonS3Service,to_destroy=True, to_build=True)]
)
class AssetService(_service.BaseService,SchedulerInterface):
    
    non_obj_template = {'globals.json','README.MD'}

    def __init__(self,hcVaultService:HCVaultService,redisService :RedisService, fileService: FileService, configService: ConfigService,amazonS3Service:AmazonS3Service,settingService:SettingService,processWorkerPeer:UvicornWorkerService) -> None:
        super().__init__()
        SchedulerInterface.__init__(self,)

        self.fileService:FileService = fileService
        self.configService = configService
        self.processWorkerPeer = processWorkerPeer
        self.amazonS3Service = amazonS3Service
        self.settingService = settingService
        self.hcVaultService = hcVaultService
        self.redisService = redisService

        self.ASSETS_GLOBALS_VARIABLES =f"{self.configService.ASSETS_DIR}globals.json"
        self.objects:list[Object] = []
        self.buckets_size = 0
        self.download_cache = IntegrityCache('value')
        self.asset_cache = IntegrityCache('value')

        self.images:dict[str,Asset] = {}
        self.css:dict[str,Asset] = {}
        self.email:dict[str,Asset] = {}
        self.pdf:dict[str,Asset] = {}
        self.phone:dict[str,Asset] = {}
        self.sms:dict[str,Asset] = {}

        self.interval_schedule(IntervalParams(hours=1,minutes=randint(0,60)),self.clear_object_events,tuple(),{})

    async def clear_object_events(self,):
        objects_events = await self.redisService.hash_iter(RedisConstant.EVENT_DB,MinioConstant.MINIO_EVENT,iter=False)
        print(objects_events)
        await self.redisService.hash_del(RedisConstant.EVENT_DB,MinioConstant.MINIO_EVENT,*objects_events.keys())

    def _read_globals_disk(self):

        try:
            self.globals =  JSONFile(self.ASSETS_GLOBALS_VARIABLES)
        except:
            self.globals = JSONFile(self.ASSETS_GLOBALS_VARIABLES,{})
        
        MLTemplate._globals.update(flatten_dict(self.globals.data))
    
    def _read_globals_s3(self):
        data = self.amazonS3Service.read_object('globals.json')
        data = json.loads(data.read())
        self.globals = JSONFile(self.ASSETS_GLOBALS_VARIABLES, data,False)

        MLTemplate._globals.update(flatten_dict(self.globals.data))
     
    def build(self,build_state=_service.DEFAULT_BUILD_STATE):
        self.read_bucket_metadata()

        match build_state:
            case _service.GUNICORN_BUILD_STATE:
                if self.configService.ASSET_MODE == AssetMode.s3 and self.configService.S3_TO_DISK:
                    self.download_into_disk()
            
            case _service.DEFAULT_BUILD_STATE:
                Template.LANG = self.settingService.ASSET_LANG
                if self.configService.ASSET_MODE == AssetMode.s3 and not self.configService.S3_TO_DISK:
                    self.read_asset_from_s3()
                else:
                    self.read_asset_from_disk()
            
            case aws_service.MINIO_OBJECT_BUILD_STATE:
                self.download_into_disk()

        self.service_status = _service.ServiceStatus.AVAILABLE
        
    def verify_dependency(self):
        if self.configService.ASSET_MODE == AssetMode.s3:
            if not self.amazonS3Service.service_status == _service.ServiceStatus.AVAILABLE:
                raise _service.BuildFailureError('Amazon S3 Service not available')

    def read_asset_from_s3(self):
        self._read_globals_s3()

        self.images.update(S3ObjectReader(self.configService,self.amazonS3Service,self.hcVaultService,self.objects,self.asset_cache,self.fileService)(
            Extension.JPEG,FDFlag.READ_BYTES,AssetType.IMAGES.value))
        self.css.update(S3ObjectReader(self.configService,self.amazonS3Service,self.hcVaultService,self.objects,self.asset_cache,self.fileService)(
            Extension.CSS,...,AssetType.EMAIL.value))

        self.email.update(S3ObjectReader(self.configService,self.amazonS3Service,self.hcVaultService,self.objects,self.asset_cache,self.fileService,HTMLTemplate,self.loadHTMLData('s3'))(
            Extension.HTML,...,AssetType.EMAIL.value))
        self.pdf.update(S3ObjectReader(self.configService,self.amazonS3Service,self.hcVaultService,self.objects,self.asset_cache,self.fileService,PDFTemplate)(
            Extension.PDF,FDFlag.READ_BYTES,AssetType.PDF.value))
        self.sms.update(S3ObjectReader(self.configService,self.amazonS3Service,self.hcVaultService,self.objects,self.asset_cache,self.fileService,SMSTemplate)(
            Extension.XML,...,AssetType.SMS.value))
        self.phone.update(S3ObjectReader(self.configService,self.amazonS3Service,self.hcVaultService,self.objects,self.asset_cache,self.fileService,PhoneTemplate)(
            Extension.XML,...,AssetType.PHONE.value))

    def read_bucket_metadata(self):
        self.buckets_size = 0
        for obj in self.amazonS3Service.list_objects(recursive=True):
            if obj.size:
                self.buckets_size += obj.size
            if obj.object_name not in self.non_obj_template:
                self.objects.append(obj)
        
    def read_asset_from_disk(self):
        self._read_globals_disk()

        if self.configService.celery_env in [CeleryMode.flower,CeleryMode.beat]:
            return 
        
        self.images.update(self.sanitize_paths(DiskReader(self.configService,self.fileService,self.asset_cache)(Extension.JPEG, FDFlag.READ_BYTES, AssetType.IMAGES.value)))
        self.css.update(self.sanitize_paths(DiskReader(self.configService,self.fileService,self.asset_cache)(Extension.CSS, FDFlag.READ, AssetType.EMAIL.value)))

        self.email.update(self.sanitize_paths(DiskReader(self.configService,self.fileService,self.asset_cache,HTMLTemplate, self.loadHTMLData('disk'))(Extension.HTML, FDFlag.READ, AssetType.EMAIL.value)))
        self.pdf.update(self.sanitize_paths(DiskReader(self.configService,self.fileService,self.asset_cache,PDFTemplate)(Extension.PDF, FDFlag.READ_BYTES, AssetType.PDF.value)))
        self.sms.update(self.sanitize_paths(DiskReader(self.configService,self.fileService,self.asset_cache,SMSTemplate)(Extension.XML, FDFlag.READ, AssetType.SMS.value)))
        self.phone.update(self.sanitize_paths(DiskReader(self.configService,self.fileService,self.asset_cache,PhoneTemplate)(Extension.XML, FDFlag.READ, AssetType.PHONE.value)))
    
    def sanitize_paths(self,assets:dict[str,Asset]):
        temp: dict[str,Asset]={}
        for key, asset in assets.items():
            key = self.configService.normalize_assets_path(key,'remove',True)
            key = key.replace(DIRECTORY_SEPARATOR,ASSET_SEPARATOR)
            temp[key]=asset
        return temp

    def loadHTMLData(self,iterator:Literal['disk','s3']):
        non_marker_obj = [obj for obj in self.objects if not obj.is_delete_marker]

        def callback(html: HTMLTemplate):
            if iterator == 'disk':  
                cssInPath = self.fileService.listExtensionPath(html.dirName, Extension.CSS.value)
            else:
                cssInPath = self.fileService.root_to_path_matching(non_marker_obj,html.dirName,Extension.CSS.value,sep=ASSET_SEPARATOR,pointer=PointerIterator('object_name'))
            
            css_content=""

            for cssPath in cssInPath:
                if not cssPath.startswith(AssetType.EMAIL.value+ASSET_SEPARATOR):
                    cssPath = f"{AssetType.EMAIL.value}{ASSET_SEPARATOR}{cssPath}"
                try:
                    css_content += self.css[cssPath].content
                except KeyError as e:
                    print(cssPath,'error')
                    continue
            
            html.loadCSS(css_content)

            if iterator == 'disk':
                imagesInPath = self.fileService.listExtensionPath(html.dirName, Extension.JPEG.value)
            else:
                imagesInPath = self.fileService.root_to_path_matching(non_marker_obj,html.dirName,Extension.JPEG.value,sep=ASSET_SEPARATOR,pointer=PointerIterator('object_name'))
                
            for imagesPath in imagesInPath:
                try:
                    imageContent = self.images[imagesPath].content
                    html.loadImage(imagesPath,imageContent)
                    continue
                except KeyError as e:
                    pass
        
            html.add_tracking_pixel()
            html.add_signature()
            html.set_content()
        
        return callback
    
    def exportRouteName(self,attributeName:RouteAssetType)-> list[str] | None:
        """
        html: HTML Template Key
        sms: SMS Template Key
        phone: Phone Template Key
        """
        try:
            if attributeName not in get_args(RouteAssetType):
                raise AttributeError
            temp:dict[str,Asset] = getattr(self,attributeName)
            if type(temp) is not dict:
                raise TypeError()
            return list(temp.keys())
        except TypeError as e:
            return None
        except KeyError as e:
            return None
        except AttributeError as e:
            pass

    def asset_rel_path(self,path,asset_type:AssetType=None):
        if asset_type is None:
            return path
        return f"{asset_type}/{path}"

    def verify_content_asset_permission(self,content:dict,model_keys:list[str],authPermission:AuthPermission,options:list[Callable[[str,str],bool]]):
                
        for keys in model_keys:
            s_content=content[keys]
            if type(s_content) == list:
                for c in s_content:
                    if type(c) == str:
                        self._raw_verify_asset_permission(c,authPermission['allowed_assets'],options)
                    
            elif type(s_content)==str:
                self._raw_verify_asset_permission(s_content,authPermission['allowed_assets'],options)           
            else:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail={'message':'Entity not properly accessed'})
        
        return True
    
    def verify_asset_permission(self,template:str,authPermission:AuthPermission,template_type:str|None,options:list[Callable[[str,list[str]],str|None]],):
        
        if template_type:
            template = self.asset_rel_path(template,template_type)
        
        self._raw_verify_asset_permission(template,authPermission['allowed_assets'],template,options)

        for option in options:
            if not option(template,authPermission):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail={'message':f'Assets [{template}] not allowed' })

    def _raw_verify_asset_permission(self,authPermission:AuthPermission,template:str,options:list[Callable[[list[str],str],str|None]],_raise=True):
        
        assetsPermission:AssetsPermission = authPermission['allowed_assets']
        allowed_files = assetsPermission['files']
        allowed_dirs = tuple(assetsPermission['dirs'])
        
        if template.startswith(allowed_dirs):
            return  True
        
        if template not in allowed_files:
            if _raise:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail={'message':f'Assets [{template}] not allowed' })
            return False
        
        for option in options:
            mess =  option(assetsPermission,template)
            if mess == None:
                continue
            else:
                if _raise:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail={'message':f'Assets [{template}] not allowed','description':mess })
                else:
                    return False
        
        return True
                    
    def get_assets_dict_by_path(self,path:str):
        
        if path.startswith(AssetType.EMAIL.value):
            return self.email
        if path.startswith(AssetType.IMAGES.value):
            return self.images
        if path.startswith(AssetType.PDF.value):
            return self.pdf
        if path.startswith(AssetType.PHONE.value):
            return self.phone
        if path.startswith(AssetType.SMS.value):
            return self.sms

        raise AssetNotFoundError

    def destroy(self,destroy_state=-1):
        pass
    
    def get_schema(self,asset:RouteAssetType):
        try:
            schemas:dict[str,MLTemplate] =getattr(self,asset)
        except AttributeError:
            raise AssetTypeNotFoundError
        return {key:value.schema for key,value in schemas.items() }

    @RunInThreadPool      
    async def save_globals(self):
        if self.configService.ASSET_MODE == AssetMode.s3:
            data = self.globals.export()
            await self.amazonS3Service.upload_object('globals.json',data)
        else:
            self.globals.save()
    
    def download_into_disk(self):
       
        for obj in self.objects:
            if obj.metadata and obj.metadata.get(MinioConstant.ENCRYPTED_KEY,False):
                continue
            
            if not self.fileService.soft_is_file(obj.object_name):
                continue

            if self.download_cache.cache(obj.object_name,obj.etag):
                continue

            disk_rel_path = self.configService.normalize_assets_path(obj.object_name,'add',True)
            self.amazonS3Service.write_into_disk(obj.object_name,disk_rel_path)
            