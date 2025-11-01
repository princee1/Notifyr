from io import BytesIO
from typing import Annotated
import zipfile
from aiohttp_retry import List
from fastapi import BackgroundTasks, Body, Depends, File, HTTPException, Query, Request, Response, UploadFile,status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.classes.auth_permission import AuthPermission,Role, filter_asset_permission
from app.classes.template import Extension, HTMLTemplate, PhoneTemplate, SMSTemplate, TemplateNotFoundError
from app.container import Get, InjectInMethod
from app.decorators.guards import GlobalsTemplateGuard
from app.decorators.handlers import FileNamingHandler, S3Handler, ServiceAvailabilityHandler, TemplateHandler, VaultHandler
from app.decorators.permissions import AdminPermission, JWTAssetPermission, JWTRouteHTTPPermission
from app.decorators.pipes import ObjectS3OperationResponsePipe, TemplateParamsPipe, ValidFreeInputTemplatePipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, UseGuard, UseHandler, UsePermission, UsePipe, UseRoles, UseServiceLock
from app.definition._utils_decorator import Guard
from app.depends.class_dep import ObjectsSearch
from app.depends.dependencies import get_auth_permission
from app.services.assets_service import EXTENSION_TO_ASSET_TYPE, AssetConfusionError, AssetService, AssetType, AssetTypeNotAllowedError
from app.services import AmazonS3Service
from app.services.config_service import ConfigService
from app.services.file_service import FileService
from app.services.secret_service import HCVaultService
from app.utils.constant import SECONDS_IN_AN_HOUR as HOUR, MinioConstant, VaultConstant
from app.utils.fileIO import ExtensionNotAllowedError, MultipleExtensionError
from app.depends.variables import force_update_query
from app.utils.helper import b64_encode

# limit the size with a guard
# limit the minio size also 

@UseRoles([Role.ASSETS])
@UseHandler(ServiceAvailabilityHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('objects')
class S3ObjectRessource(BaseHTTPRessource):
    
    class UploadGuard(Guard):

        def __init__(self,max_file:int,max_file_size=int):
            super().__init__()        
            self.max_file = max_file
            self.max_file_size = max_file_size
            self.configService = Get(ConfigService)
            self.assetService = Get(AssetService)
    
    @staticmethod
    def pipe_restore(restore:bool,template:str,objectsSearch:ObjectsSearch):
        if restore:
            if objectsSearch.version_id == None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST,'Version id is needed to restore from a previous version')
            
            return {'destination_template':template,'move':False}
        return {}

    @staticmethod
    async def is_minio_external_guard():
        s3Service = Get(AmazonS3Service)
        return s3Service.external, '' if s3Service.external else 'Cannot generate presigned url for a non external s3 endpoint'

    @InjectInMethod()
    def __init__(self, assetService: AssetService, amazonS3Service: AmazonS3Service, hcVaultService: HCVaultService,fileService:FileService):
        super().__init__()
        self.assetService: AssetService = assetService
        self.amazonS3Service: AmazonS3Service = amazonS3Service
        self.hcVaultService: HCVaultService = hcVaultService
        self.fileService = fileService

        self.is_asset_pipe= TemplateParamsPipe(accept_none=False,inject_asset_routes=True)
        self.free_input_pipe = ValidFreeInputTemplatePipe(False,True)

    async def upload(self, files:list[UploadFile | dict],encrypt:bool=False):
        
        for file in files:
            if type(file) == UploadFile:
                file_bytes = await file.read()
                filename = file.filename
            else:
                file_bytes = file['content']
                filename = file['filename']

            ext = self.fileService.get_extension(filename)
            if ext == Extension.HTML.value:
                ...
                #file_bytes = self.fileService.html_minify(file_bytes)
            metadata= None
            if encrypt:
                file_bytes = file_bytes.decode()
                file_bytes = self.hcVaultService.transit_engine.encrypt(file_bytes,'s3-rest-key')
                file_bytes = file_bytes.encode()

                metadata = {MinioConstant.ENCRYPTED_KEY:True}
            
            await self.amazonS3Service.upload_object(filename,file_bytes,metadata=metadata)

    @UsePermission(AdminPermission)
    @PingService([HCVaultService])
    @UseServiceLock(HCVaultService,lockType='reader',check_status=False)
    @UseGuard(is_minio_external_guard)
    @BaseHTTPRessource.HTTPRoute('/generate-url/',methods=[HTTPMethod.GET,HTTPMethod.PUT])
    def generate_url(self,request:Request,expiry:int=Query(3600,ge=6*60,le=HOUR*2),version:str=Query(None)): # type: ignore
        method = request.method
        url = self.amazonS3Service.generate_presigned_url(method=method,expiry=expiry,version_id=version)
        return {
            'presigned_url':url,
            'expiry':expiry,
            'method':method
        }
    

    @UsePermission(AdminPermission)
    @UseHandler(FileNamingHandler,S3Handler,VaultHandler)
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
                self.fileService.is_file(filename,allowed_extensions=ValidFreeInputTemplatePipe.allowed_extension)
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


    @UsePermission(JWTAssetPermission(accept_none_template=True))
    @UseHandler(S3Handler,VaultHandler,FileNamingHandler)
    @PingService([AmazonS3Service,HCVaultService])
    @UsePipe(ValidFreeInputTemplatePipe)
    @UseServiceLock(HCVaultService,AmazonS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/download/{template:path}',methods=[HTTPMethod.GET],mount=False)
    async def download_stream(self,request:Request,template:str,objectSearch:Annotated[ObjectsSearch,Depends(ObjectsSearch)],authPermission:AuthPermission=Depends(get_auth_permission)): # type: ignore

        if objectSearch.is_file:
            objects = self.amazonS3Service.read_object(template,objectSearch.version_id)
            attachment_name = template
        else:
            files = self.amazonS3Service.download_objects(template,objectSearch.recursive,objectSearch.match)
            objects = BytesIO()
            with zipfile.ZipFile(objects, "w") as zip_file:
                for filename, data in files.items():
                    zip_file.writestr(filename, data)
            objects.seek(0)
            attachment_name = template if not template.endswith('/') else template[:-1] + '.zip'

        return StreamingResponse(
            objects,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={attachment_name}"}
        )

    @UsePermission(AdminPermission)
    @PingService([AmazonS3Service])
    @UseHandler(S3Handler)
    @UseGuard(GlobalsTemplateGuard)
    @UsePipe(ObjectS3OperationResponsePipe,before=False)
    @UsePipe(ValidFreeInputTemplatePipe(False,True))
    @UseServiceLock(AmazonS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/{template:path}',methods=[HTTPMethod.DELETE],response_model=ObjectS3OperationResponsePipe.ResponseModel)
    def delete_object(self,template:str,response:Response,request:Request,objectsSearch:Annotated[ObjectsSearch,Depends(ObjectsSearch)],force:bool=Query(False),authPermission:AuthPermission=Depends(get_auth_permission)):
        
        if objectsSearch.version_id:
            meta = self.amazonS3Service.delete_object(template,version_id=objectsSearch.version_id) 
            if meta.is_delete_marker: # NOTE the user deleted the marker object and rollback to the latest version
                response.status_code = status.HTTP_201_CREATED     
            return {'meta':meta}
        else:
            if objectsSearch.is_file:
                objectsSearch.recursive = False
                objectsSearch.match = None
            return self.amazonS3Service.delete_objects_prefix(template,objectsSearch.recursive,objectsSearch.match,force)


    @PingService([AmazonS3Service,HCVaultService])
    @UseRoles(roles=[Role.PUBLIC])
    @UseHandler(S3Handler,VaultHandler,FileNamingHandler,TemplateHandler)
    @UsePermission(JWTAssetPermission)
    @UsePipe(ObjectS3OperationResponsePipe,before=False)
    @UseGuard(GlobalsTemplateGuard('We cannot read the object globals.json at this route please use refer to properties/global route'))
    @UseServiceLock(HCVaultService,AmazonS3Service,AssetService,lockType='reader',check_status=False)
    @UsePipe(ValidFreeInputTemplatePipe(False,False))
    @BaseHTTPRessource.HTTPRoute('/single/{template:path}',methods=[HTTPMethod.GET],response_model=ObjectS3OperationResponsePipe.ResponseModel)
    async def read_object(self,template:str,request:Request,objectsSearch:Annotated[ObjectsSearch,Depends(ObjectsSearch)],authPermission:AuthPermission=Depends(get_auth_permission)):
        ext = self.fileService.get_extension(template)

        if objectsSearch.assets and ext==Extension.HTML.value:
            asset_routes = await self.is_asset_pipe.pipe(template)
            template:HTMLTemplate = asset_routes[template]
            content = template.content
        else:
            objects = self.amazonS3Service.read_object(template,objectsSearch.version_id) 
            content = objects.read().decode()
            objects.close()

        content = b64_encode(content)
        return {'content':content}


    @PingService([AmazonS3Service])
    @UseRoles(roles=[Role.PUBLIC])
    @UsePipe(ObjectS3OperationResponsePipe,before=False)
    @UseServiceLock(AmazonS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/all/',methods=[HTTPMethod.GET])
    def list_objects_stat(self,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        objects = self.assetService.objects.copy()
        if authPermission != None:
            filter_asset_permission(authPermission)
            objects = [o for o in objects 
                    if self.assetService._raw_verify_asset_permission(authPermission,o.object_name,_raise=False)
                    ]
        return {
            'meta':objects
        }

                
    @PingService([AmazonS3Service,HCVaultService])
    @UsePermission(AdminPermission)
    @UseHandler(S3Handler,VaultHandler,TemplateHandler,FileNamingHandler)
    @UseGuard(GlobalsTemplateGuard)
    @UsePipe(ObjectS3OperationResponsePipe,before=False)
    @UsePipe(ValidFreeInputTemplatePipe(False,False,{'.xml','.html','.css','.scss'},{'email','phone','sms'}))
    @UseServiceLock(HCVaultService,AmazonS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/{template:path}',methods=[HTTPMethod.PUT],response_model=ObjectS3OperationResponsePipe.ResponseModel)
    def modify_object(self,template:str,request:Request,backgroundTask:BackgroundTasks,objectsSearch:Annotated[ObjectsSearch,Depends(ObjectsSearch)],content: str = Body(..., media_type="text/plain"),authPermission:AuthPermission=Depends(get_auth_permission)):
        meta= self.amazonS3Service.stat_objet(template,objectsSearch.version_id,True)
        encrypted = meta.metadata.get(MinioConstant.ENCRYPTED_KEY,False) if meta.metadata else False
        assetType = template.split('/')[0]
        extension = self.fileService.get_extension(template)
        match assetType:
            case 'email': HTMLTemplate('',content,'') if extension == Extension.HTML.value else ...
            case 'phone': PhoneTemplate('',content,'')
            case 'sms': SMSTemplate('',content,'')

        backgroundTask.add_task(self.upload,[{'content':content.encode(),'filename':template}],False)
        return {
            'meta':meta,
        }
    

    @PingService([AmazonS3Service])
    @UseHandler(S3Handler,FileNamingHandler)
    @UsePermission(AdminPermission)
    @UsePipe(ObjectS3OperationResponsePipe,before=False)
    @UsePipe(pipe_restore,ValidFreeInputTemplatePipe(False,False))
    @UseGuard(GlobalsTemplateGuard)
    @UseServiceLock(AmazonS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/{template:path}/to/{destination_template:path}',methods=[HTTPMethod.PATCH],response_model=ObjectS3OperationResponsePipe.ResponseModel,mount=False)
    def copy_object(self,template:str,request:Request,destination_template:str,objectsSearch:Annotated[ObjectsSearch,Depends(ObjectsSearch)],move:bool = Query(False),restore:bool = Query(False),authPermission:AuthPermission=Depends(get_auth_permission)):

        self.free_input_pipe.pipe(destination_template,objectsSearch)
        if objectsSearch.is_file:
            if self.fileService.get_extension(template) != self.fileService.get_extension(destination_template):
                raise ExtensionNotAllowedError('Extension of the destination_template should be the same as the template')    
        else:
            destination_template  = destination_template if destination_template.endswith('/') else destination_template+ "/" 
            destination_template += self.fileService.soft_get_filename(template)
        
        if template.split('/')[0] !=  destination_template.split('/')[0]:
            raise AssetTypeNotAllowedError
    
        return self.amazonS3Service.copy_object(template,destination_template,objectsSearch.version_id,move)

    
    
