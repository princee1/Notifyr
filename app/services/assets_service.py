from fastapi import HTTPException,status

from app.definition._error import BaseError
from app.services.aws_service import AmazonS3Service
from app.utils.prettyprint import printJSON
from .config_service import CeleryMode, ConfigService
from app.utils.fileIO import FDFlag, JSONFile
from app.classes.template import Asset, HTMLTemplate, MLTemplate, PDFTemplate, SMSTemplate, PhoneTemplate, SkipTemplateCreationError, Template
from .security_service import SecurityService
from .file_service import FileService, FTPService
from app.definition import _service
from injector import inject
from enum import Enum
import os
from threading import Thread
from typing import Any, Callable, Literal, Dict
from app.utils.helper import flatten_dict, issubclass_of

ROOT_PATH = "assets/"
DIRECTORY_SEPARATOR = '\\'
REQUEST_DIRECTORY_SEPARATOR = ':'
ASSETS_GLOBALS_VARIABLES =f"{ROOT_PATH}globals.json"


def path(x): return ROOT_PATH+x

class AssetNotFoundError(BaseError):
    ...

class AssetTypeNotFoundError(BaseError):
    ...

class Extension(Enum):
    """
    The class `Extension` defines an enumeration of file extensions.
    """

    HTML = "html"
    CSS = "css"
    SCSS = "scss"
    JPEG = "jpg"
    PDF = "pdf"
    TXT = "txt"
    XML= "xml"


class AssetType(Enum):
    IMAGES = "images"
    PDF = "pdf"
    SMS = "sms"
    PHONE = "phone"
    HTML = Extension.HTML.value
    
RouteAssetType = Literal['html', 'sms', 'phone']

def extension(extension: Extension): return f".{extension.value}"


class Reader():
    fileService: FileService

    def __init__(self, asset: type[Asset] = Asset, additionalCode: Callable = None) -> None:
        self.asset = asset
        self.values: Dict[str, Asset] = {}
        self.func = additionalCode

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
        extension_ = extension(ext)
        root = path(rootParam) if type(rootParam) is str  else path(ext.value)
        setTempFile: set[str] = set()
        for file in self.fileService.listFileExtensions(extension_, root, recursive=True):
            relpath = root + os.path.sep+file
            filename, content, dir = self.fileService.readFileDetail(
                relpath, flag, encoding)
            keyName = filename if not setTempFile else file
            setTempFile.add(keyName)
            try:
                self.values[relpath] = self.asset(keyName, content, dir)
            except SkipTemplateCreationError as e:
                print(e.args[0])
                #printJSON(e.args[1])
            except Exception as e :
                print(e.__class__,e)

            if issubclass_of(Template, self.asset):
                if self.func != None:
                    self.func(self.values[relpath])

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        """
        :param ext:
        :type ext: Extension

        :param flag:
        :type flag: FDFlag

        :param rootFlag: 

        :param encoding:
        """
        self.safeReader(*args)
        return self.values


class ThreadedReader(Reader):
    def __init__(self, asset: Asset = Asset, additionalCode: Callable[..., Any] = None) -> None:
        super().__init__(asset, additionalCode)
        self.thread: Thread

    def read(self, ext: Extension, flag: FDFlag, rootFlag: bool | str = True, encoding="utf-8"):
        self.thread = Thread(target=super().read, args=(ext, flag, rootFlag, encoding))
        self.thread.start()

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        self.safeReader(*args)
        return self

    def join(self):
        self.thread.join()
        return self.values


@_service.PossibleDep([FTPService])
@_service.Service
class AssetService(_service.BaseService):
    @inject
    def __init__(self, fileService: FileService, securityService: SecurityService, configService: ConfigService,amazonS3Service:AmazonS3Service) -> None:
        super().__init__()
        self.fileService = fileService
        self.fileService:FileService = fileService
        self.securityService = securityService
        self.configService = configService
        self.amazonS3Service = amazonS3Service

    def _read_globals(self):

        try:
            self.globals =  JSONFile(ASSETS_GLOBALS_VARIABLES)
        except:
            self.globals = JSONFile(ASSETS_GLOBALS_VARIABLES,{})
        
        MLTemplate._globals.update(flatten_dict(self.globals.data))

        
    def build(self,build_state=-1):
        
        self._read_globals()

        Template.LANG = self.configService.ASSET_LANG

        self.images: dict[str, Asset] = {}
        self.css: dict[str, Asset] = {}

        self.html: dict[str, HTMLTemplate] = {}
        self.pdf: dict[str, PDFTemplate] = {}
        self.sms: dict[str, SMSTemplate] = {}
        self.phone: dict[str, PhoneTemplate] = {}

        Reader.fileService = self.fileService
        if self.configService.celery_env in [CeleryMode.flower,CeleryMode.beat]:
            return 
        
        self.images = Reader()(Extension.JPEG, FDFlag.READ_BYTES, AssetType.IMAGES.value)
        self.css = Reader()(Extension.CSS, FDFlag.READ, AssetType.HTML.value)

        htmlReader = Reader(HTMLTemplate, self.loadHTMLData)(Extension.HTML, FDFlag.READ, AssetType.HTML.value)
        pdfReader = Reader(PDFTemplate)(Extension.PDF, FDFlag.READ_BYTES, AssetType.PDF.value)
        smsReader = Reader(SMSTemplate)(Extension.XML, FDFlag.READ, AssetType.SMS.value)
        phoneReader = Reader(PhoneTemplate)(Extension.XML, FDFlag.READ, AssetType.PHONE.value)

        self.html = htmlReader
        self.pdf = pdfReader
        self.sms = smsReader
        self.phone = phoneReader

        self.service_status = _service.ServiceStatus.AVAILABLE
        
    def loadHTMLData(self, html: HTMLTemplate):
        cssInPath = self.fileService.listExtensionPath(html.dirName, Extension.CSS.value)
        css_content=""
        for cssPath in cssInPath:
            cssPath = self.asset_rel_path(cssPath,Extension.HTML.value)
            cssPath = cssPath.replace(Extension.CSS.value+"\\",'')
            cssPath = cssPath.replace(Extension.HTML.value+"\\"+Extension.HTML.value+"\\",Extension.HTML.value+"\\")
            try:
                css_content += self.css[cssPath].content
                
            except KeyError as e:
                print('error')
                pass
        html.loadCSS(css_content)
        imagesInPath = self.fileService.listExtensionPath(html.dirName, Extension.JPEG.value)
        for imagesPath in imagesInPath:
            try:
                imageContent = self.images[imagesPath].content
                html.loadImage(imagesPath,imageContent)
            except KeyError as e:
                pass
       
        html.add_tracking_pixel()
        html.add_signature()
        html.set_content()
        

    def exportRouteName(self,attributeName:RouteAssetType)-> list[str] | None:
        """
        html: HTML Template Key
        sms: SMS Template Key
        phone: Phone Template Key
        """
        try:
            if attributeName != "html" and  attributeName !="sms" and attributeName != "phone":
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

    def asset_rel_path(self,path,asset_type):
        return f"{self.configService.ASSET_DIR}{asset_type}\\{path}"
        
    def verify_asset_permission(self,content:dict,model_keys:list[str],assetPermission,options:list[Callable[[Any],bool]]):
        
        permission = tuple(assetPermission)
        for keys in model_keys:
            s_content=content[keys]
            if type(s_content) == list:
                for c in s_content:
                    if type(c) == str:
                        if not c.startswith(permission):
                            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail={'message':f'Assets [{c}] not allowed' })
                    
            elif type(s_content)==str:
                if not c.startswith(permission):
                            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail={'message':f'Assets [{s_content}] not allowed' })      
            else:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail={'message':'Entity not properly accessed'})
            
            for option in options:
                if not option(assetPermission):
                    return False

        return True
    
    def destroy(self,destroy_state=-1):
        pass

    def encryptPdf(self, name):
        KEY=""
        self.pdf[name].encrypt(KEY)

    def check_asset(self,asset, allowed_assets:list[str]=None):
        if asset == None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail='Asset not specified')

        if allowed_assets == None and asset != "html" and  asset !="sms" and asset != "phone":
            raise AssetNotFoundError(asset)
        
        return asset in allowed_assets
    
    def get_schema(self,asset:RouteAssetType):
        try:
            schemas:dict[str,MLTemplate] =getattr(self,asset)
        except AttributeError:
            raise AssetTypeNotFoundError
        return {key:value.schema for key,value in schemas.items() }
            
