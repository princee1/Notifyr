from typing import Callable
from aiohttp_retry import List
from fastapi import BackgroundTasks, Depends, File, HTTPException, Query, Request, Response, UploadFile,status
from app.classes.auth_permission import AuthPermission, MustHave, MustHaveRoleSuchAs, Role
from app.classes.template import Extension
from app.container import Get, InjectInMethod
from app.decorators.guards import GlobalsTemplateGuard
from app.decorators.handlers import S3Handler, ServiceAvailabilityHandler, VaultHandler
from app.decorators.permissions import AdminPermission, JWTAssetPermission, JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, UseGuard, UseHandler, UseLimiter, UsePermission, UseRoles, UseServiceLock
from app.definition._utils_decorator import Guard
from app.depends.dependencies import get_auth_permission
from app.services.assets_service import EXTENSION_TO_ASSET_TYPE, AssetConfusionError, AssetService, AssetType, AssetTypeNotAllowedError, AssetTypeNotFoundError
from app.services import AmazonS3Service
from app.services.config_service import ConfigService
from app.services.file_service import FileService
from app.services.secret_service import HCVaultService
from app.utils.constant import SECONDS_IN_AN_HOUR as HOUR, MinioConstant, VaultConstant
from app.utils.fileIO import ExtensionNotAllowedError, MultipleExtensionError
from app.depends.variables import force_update_query

# limit the size with a guard
# limit the minio size also 


async def upload_handler(function: Callable, *args, **kwargs):
    try:
        return await function(*args, **kwargs)

    except AssetTypeNotAllowedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Asset type not allowed for upload."
        )

    except AssetTypeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset type not found."
        )

    except MultipleExtensionError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Multiple file extensions detected; only one is allowed."
        )

    except ExtensionNotAllowedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The file extension is not allowed for this asset type."
        )
    except AssetConfusionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"XML asset filenames must start with either of those values '{e.asset_confusion}'. Received: '{e.filename}'"
        )

class UploadGuard(Guard):

    def __init__(self,max_file:int,max_file_size=int):
        super().__init__()        
        self.max_file = max_file
        self.max_file_size = max_file_size
        self.configService = Get(ConfigService)
        self.assetService = Get(AssetService)
    
async def is_minio_external_guard():
    s3Service = Get(AmazonS3Service)
    return s3Service.external, '' if s3Service.external else 'Cannot generate presigned url for a non external s3 endpoint'

@UseRoles([Role.ASSETS])
@UseHandler(ServiceAvailabilityHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('objects')
class S3ObjectRessource(BaseHTTPRessource):

    allowed_extension = set(Extension._value2member_map_.keys())
    
    @InjectInMethod()
    def __init__(self, assetService: AssetService, amazonS3Service: AmazonS3Service, hcVaultService: HCVaultService,fileService:FileService):
        super().__init__()
        self.assetService: AssetService = assetService
        self.amazonS3Service: AmazonS3Service = amazonS3Service
        self.hcVaultService: HCVaultService = hcVaultService
        self.fileService = fileService

    async def upload(self, files:list[UploadFile],encrypt:bool=False):
        
        for file in files:
            file_bytes = await file.read()
            metadata= None
            if encrypt:
                file_bytes = file_bytes.decode()
                file_bytes = self.hcVaultService.transit_engine.encrypt(file_bytes,'s3-rest-key')
                file_bytes = file_bytes.encode()

                metadata = {MinioConstant.ENCRYPTED_KEY:True}
            
            await self.amazonS3Service.upload_object(file.filename,file_bytes,metadata=metadata)


    @UsePermission(AdminPermission)
    @PingService([HCVaultService])
    @UseServiceLock(HCVaultService,lockType='reader',check_status=False)
    @UseGuard(is_minio_external_guard)
    @BaseHTTPRessource.HTTPRoute('/generate-url/',methods=[HTTPMethod.GET,HTTPMethod.PUT])
    def generate_url(self,request:Request,expiry:int=Query(3600,ge=6*60,le=HOUR*2),version:str=Query(None)): # type: ignore
        method = request.method
        self.amazonS3Service.generate_presigned_url(method=method,expiry=expiry,version_id=version)
    
    @UsePermission(AdminPermission)
    @UseHandler(upload_handler,S3Handler,VaultHandler)
    @PingService([AmazonS3Service])
    @UseGuard(GlobalsTemplateGuard)
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UseServiceLock(HCVaultService,AmazonS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/upload/',methods=[HTTPMethod.POST])
    async def upload_stream(self,request:Request,response:Response,backgroundTask:BackgroundTasks,files: List[UploadFile] = File(...),force:bool= Depends(force_update_query),encrypt:bool=Query(False), authPermission:AuthPermission=Depends(get_auth_permission)):
        
        errors = {}
        upload_files:list[UploadFile]= []

        for file in files:
            filename = file.filename
            ext = self.fileService.get_extension(ext)
            try:
                self.fileService.is_file(filename,allowed_extensions=self.allowed_extension)
            except (MultipleExtensionError,ExtensionNotAllowedError) as e:
                if force:
                    errors[filename]= {'name':e.__class__.__name__,'description':e.mess}
                    continue
                else: raise e
            
            if ext == Extension.XML.value and not filename.startswith(AssetConfusionError.asset_confusion):
                if force:
                    errors[filename]={'name':AssetConfusionError.__name__,'description':"filename must start with either phone or sms"} 
                    continue
                else:raise AssetConfusionError(filename)

            asset_type = EXTENSION_TO_ASSET_TYPE[ext]
            file.filename = f"{asset_type}/{filename}"
            upload_files.append(file)

        backgroundTask.add_task(self.upload,upload_files)# TODO encrypt files
        return {
        "uploaded_files": [f.filename for f in upload_files],
        "errors": errors
        }

    @UsePermission(JWTAssetPermission)
    @UseHandler(S3Handler,VaultHandler)
    @PingService([AmazonS3Service])
    @UseServiceLock(AmazonS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/download/{template:path}',methods=[HTTPMethod.GET],mount=False)
    async def download_stream(self,request:Request,template:str,authPermission:AuthPermission=Depends(get_auth_permission)):
        is_file = self.fileService.soft_is_file(template)
        self.amazonS3Service.list_objects()

    @UsePermission(AdminPermission)
    @PingService([AmazonS3Service])
    @UseHandler(S3Handler)
    @UseGuard(GlobalsTemplateGuard)
    @UseServiceLock(AmazonS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/{template:path}',methods=[HTTPMethod.DELETE])
    def delete_object(self,template:str,request:Request,authPermission:AuthPermission=Depends(get_auth_permission)):
        ...


    @PingService([AmazonS3Service,HCVaultService])
    @UseRoles(roles=[Role.PUBLIC])
    @UseHandler(S3Handler,VaultHandler)
    @UsePermission(JWTAssetPermission)
    @UseGuard(GlobalsTemplateGuard('We cannot read the object globals.json at this route please use refer to properties/global route'))
    @UseServiceLock(HCVaultService,AmazonS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/{template:path}',methods=[HTTPMethod.GET])
    def read_object(self,template:str,request:Request,authPermission:AuthPermission=Depends(get_auth_permission)):
        ...
    
    @PingService([AmazonS3Service,HCVaultService])
    @UsePermission(AdminPermission)
    @UseHandler(S3Handler,VaultHandler)
    @UseGuard(GlobalsTemplateGuard)
    @UseServiceLock(HCVaultService,AmazonS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/{template:path}',methods=[HTTPMethod.PUT])
    def modify_object(self,template:str,authPermission:AuthPermission=Depends(get_auth_permission)):
        ...
    
    @PingService([AmazonS3Service])
    @UseHandler(S3Handler)
    @UsePermission(AdminPermission)
    @UseGuard(GlobalsTemplateGuard)
    @UseServiceLock(AmazonS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/{template:path}/to/{destination_template:path}',methods=[HTTPMethod.PATCH])
    def copy_object(self,template:str,destination_template:str,prefix:bool = Query(False),move:bool = Query(False),authPermission:AuthPermission=Depends(get_auth_permission)):
        ...

    
    
