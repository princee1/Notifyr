from io import BytesIO
from typing import Annotated
import zipfile
from aiohttp_retry import List
from fastapi import BackgroundTasks, Body, Depends, File, HTTPException, Query, Request, Response, UploadFile,status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.classes.auth_permission import AuthPermission,Role, filter_asset_permission
from app.cost.file_cost import FileCost
from app.models.object_model import ObjectResponseUploadModel, ObjectS3ResponseModel
from app.classes.template import Extension, HTMLTemplate, PhoneTemplate, SMSTemplate, TemplateNotFoundError
from app.container import Get, InjectInMethod
from app.decorators.guards import GlobalsTemplateGuard, UploadFilesGuard
from app.decorators.handlers import AsyncIOHandler, FileNamingHandler, S3Handler, ServiceAvailabilityHandler, TemplateHandler, UploadFileHandler, VaultHandler
from app.decorators.interceptors import DataCostInterceptor, ResponseCacheInterceptor
from app.decorators.permissions import AdminPermission, JWTAssetObjectPermission, JWTRouteHTTPPermission
from app.decorators.pipes import ObjectS3OperationResponsePipe, TemplateParamsPipe, ValidFreeInputTemplatePipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, IncludeRessource, PingService, UseGuard, UseHandler, UseInterceptor, UsePermission, UsePipe, UseRoles, UseServiceLock
from app.definition._service import StateProtocol
from app.definition._utils_decorator import Guard
from app.depends.class_dep import ObjectsSearch
from app.depends.dependencies import get_auth_permission
from app.depends.res_cache import MinioResponseCache
from app.manager.broker_manager import Broker
from app.services.assets_service import EXTENSION_TO_ASSET_TYPE, AssetConfusionError, AssetService, AssetType, AssetTypeNotAllowedError
from app.services import ObjectS3Service
from app.services.config_service import ConfigService
from app.services.file.file_service import FileService
from app.services.vault_service import VaultService
from app.utils.constant import SECONDS_IN_AN_HOUR as HOUR, CostConstant, MinioConstant, VaultConstant
from app.utils.fileIO import ExtensionNotAllowedError, MultipleExtensionError
from app.depends.variables import force_update_query
from app.utils.helper import b64_encode
from app.utils.tools import RunInThreadPool

# limit the size with a guard
# limit the minio size also 


@HTTPRessource('webhooks')
class S3ObjectWebhookRessource(BaseHTTPRessource):
    
    
    @InjectInMethod()
    def __init__(self,assetService:AssetService,objectS3Service:ObjectS3Service):
        super().__init__()
        self.assetService = assetService
        self.objectS3Service = objectS3Service

    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST,HTTPMethod.GET,HTTPMethod.DELETE])
    def webhooks(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)]):
        ...



@UseRoles([Role.ASSETS])
@UseHandler(ServiceAvailabilityHandler,AsyncIOHandler)
@UsePermission(JWTRouteHTTPPermission)
@IncludeRessource(S3ObjectWebhookRessource)
@HTTPRessource('objects')
class S3ObjectRessource(BaseHTTPRessource):

    @staticmethod
    def pipe_restore(restore:bool,template:str,objectsSearch:ObjectsSearch):
        if restore:
            if objectsSearch.version_id == None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST,'Version id is needed to restore from a previous version')
            
            return {'destination_template':template,'move':False}
        return {}

    @staticmethod
    async def is_minio_external_guard():
        s3Service = Get(ObjectS3Service)
        return s3Service.external, '' if s3Service.external else 'Cannot generate presigned url for a non external s3 endpoint'

    @InjectInMethod()
    def __init__(self, assetService: AssetService, objectS3Service: ObjectS3Service, hcVaultService: VaultService,fileService:FileService):
        super().__init__()
        self.assetService: AssetService = assetService
        self.objectS3Service: ObjectS3Service = objectS3Service
        self.hcVaultService: VaultService = hcVaultService
        self.fileService = fileService

        self.is_asset_pipe= TemplateParamsPipe(accept_none=False,inject_asset_routes=True)
        self.free_input_pipe = ValidFreeInputTemplatePipe(False,True)

    async def upload(self, file:UploadFile | dict,encrypt:bool=False):
        
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
            file_bytes = await RunInThreadPool(self.hcVaultService.transit_engine.encrypt)(file_bytes,'s3-rest-key')
            file_bytes = file_bytes.encode()

            metadata = {MinioConstant.ENCRYPTED_KEY:True}
            await self.objectS3Service.upload_object(filename,file_bytes,metadata=metadata)

    @UsePermission(AdminPermission)
    @UseHandler(FileNamingHandler,S3Handler,VaultHandler,UploadFileHandler)
    @PingService([ObjectS3Service])
    @UseGuard(GlobalsTemplateGuard,UploadFilesGuard())
    @UseInterceptor(DataCostInterceptor(CostConstant.OBJECT_CREDIT,'purchase'))
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UseServiceLock(VaultService,ObjectS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/upload/',methods=[HTTPMethod.POST],response_model=ObjectResponseUploadModel ,mount=False)
    async def upload_stream(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[FileCost,Depends(FileCost)],backgroundTask:BackgroundTasks,files: List[UploadFile] = File(...),force:bool= Depends(force_update_query),encrypt:bool=Query(False), authPermission:AuthPermission=Depends(get_auth_permission)):
        
        errors = {}
        upload_files = []
        meta = []
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

            meta.append((file.filename,file.size))
            file.filename = f"{EXTENSION_TO_ASSET_TYPE[ext]}/{filename}"
            upload_files.append(file.filename)
            backgroundTask.add_task(self.upload,file)

        broker.wait(len(upload_files)*2)
        broker.propagate_state(StateProtocol(service=AssetService,to_build=True,recursive=True,bypass_async_verify=False))
        return ObjectResponseUploadModel(meta=meta,uploaded_files=upload_files,errors=errors)


    @UsePermission(JWTAssetObjectPermission(accept_none_template=True))
    @UseHandler(S3Handler,VaultHandler,FileNamingHandler)
    @PingService([ObjectS3Service,VaultService])
    @UsePipe(ValidFreeInputTemplatePipe)
    @UseServiceLock(VaultService,ObjectS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/download/{template:path}',methods=[HTTPMethod.GET],mount=False)
    async def download_stream(self,request:Request,template:str,objectSearch:Annotated[ObjectsSearch,Depends(ObjectsSearch)],authPermission:AuthPermission=Depends(get_auth_permission)): # type: ignore

        if objectSearch.is_file:
            objects = await RunInThreadPool(self.objectS3Service.read_object)(template,objectSearch.version_id)
            attachment_name = template
        else:
            files = await self.objectS3Service.download_objects(template,objectSearch.recursive,objectSearch.match)
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
    @PingService([ObjectS3Service])
    @UseHandler(S3Handler)
    @UseGuard(GlobalsTemplateGuard)
    @UsePipe(ObjectS3OperationResponsePipe,before=False)
    @UsePipe(ValidFreeInputTemplatePipe(False,True))
    @UseServiceLock(ObjectS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/delete/{template:path}',methods=[HTTPMethod.DELETE],response_model=ObjectS3ResponseModel)
    async def delete_object(self,template:str,response:Response,request:Request,broker:Annotated[Broker,Depends(Broker)],objectsSearch:Annotated[ObjectsSearch,Depends(ObjectsSearch)],force:bool=Query(False),authPermission:AuthPermission=Depends(get_auth_permission)):
        
        if objectsSearch.version_id:
            meta = await self.objectS3Service.delete_object(template,version_id=objectsSearch.version_id) 
            if meta.is_delete_marker: # NOTE the user deleted the marker object and rollback to the latest version
                response.status_code = status.HTTP_201_CREATED 
            return {'meta':meta}
        else:
            if objectsSearch.is_file:
                objectsSearch.recursive = False
                objectsSearch.match = None

            broker.wait(2)
            broker.propagate_state(StateProtocol(service=AssetService,to_build=True,recursive=True,bypass_async_verify=False))
            return await self.objectS3Service.delete_objects_prefix(template,objectsSearch.recursive,objectsSearch.match,force)


    @PingService([ObjectS3Service,VaultService])
    @UseRoles(roles=[Role.PUBLIC])
    @UseHandler(S3Handler,VaultHandler,FileNamingHandler,TemplateHandler)
    @UsePermission(JWTAssetObjectPermission)
    @UsePipe(ObjectS3OperationResponsePipe,before=False)
    @UseGuard(GlobalsTemplateGuard('We cannot read the object globals.json at this route please use refer to properties/global route'))
    @UseServiceLock(VaultService,ObjectS3Service,AssetService,lockType='reader',check_status=False)
    @UsePipe(ValidFreeInputTemplatePipe(False,False))
    @UseInterceptor(ResponseCacheInterceptor('cache',MinioResponseCache,raise_default_exception=False),mount=False)
    @BaseHTTPRessource.HTTPRoute('/single/{template:path}',methods=[HTTPMethod.GET],response_model=ObjectS3ResponseModel)
    async def read_object(self,template:str,request:Request,response:Response,backgroundTasks:BackgroundTasks,objectsSearch:Annotated[ObjectsSearch,Depends(ObjectsSearch)],authPermission:AuthPermission=Depends(get_auth_permission)):
        ext = self.fileService.get_extension(template)

        if objectsSearch.assets and ext==Extension.HTML.value:
            asset_routes = await self.is_asset_pipe.pipe(template)
            template:HTMLTemplate = asset_routes[template]
            content = template.content
        else:
            objects = await RunInThreadPool(self.objectS3Service.read_object)(template,objectsSearch.version_id) 
            content = objects.read().decode()
            objects.close()

        content = b64_encode(content)
        return {'content':content}


    @PingService([ObjectS3Service])
    @UseRoles(roles=[Role.PUBLIC])
    @UsePipe(ObjectS3OperationResponsePipe,before=False)
    @UseServiceLock(ObjectS3Service,AssetService,lockType='reader',check_status=False)
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

                
    @PingService([ObjectS3Service,VaultService])
    @UsePermission(AdminPermission)
    @UseHandler(S3Handler,VaultHandler,TemplateHandler,FileNamingHandler)
    @UseGuard(GlobalsTemplateGuard)
    @UsePipe(ObjectS3OperationResponsePipe,before=False)
    @UsePipe(ValidFreeInputTemplatePipe(False,False,{'.xml','.html','.css','.scss'},{'email','phone','sms'}))
    @UseServiceLock(VaultService,ObjectS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/modify/{template:path}',methods=[HTTPMethod.PUT],response_model=ObjectS3ResponseModel,mount=False)
    async def modify_object(self,template:str,request:Request,broker:Annotated[Broker,Depends(Broker)],backgroundTask:BackgroundTasks,objectsSearch:Annotated[ObjectsSearch,Depends(ObjectsSearch)],content: str = Body(..., media_type="text/plain"),authPermission:AuthPermission=Depends(get_auth_permission)):
        meta= await self.objectS3Service.stat_objet(template,objectsSearch.version_id,True)
        encrypted = meta.metadata.get(MinioConstant.ENCRYPTED_KEY,False) if meta.metadata else False
        assetType = template.split('/')[0]
        extension = self.fileService.get_extension(template)
        match assetType:
            case 'email': HTMLTemplate('',content,'') if extension == Extension.HTML.value else ...
            case 'phone': PhoneTemplate('',content,'')
            case 'sms': SMSTemplate('',content,'')

        backgroundTask.add_task(self.upload,[{'content':content.encode(),'filename':template}],False)
        broker.wait(3)
        broker.propagate_state(StateProtocol(service=AssetService,to_build=True,recursive=True,bypass_async_verify=False))
        return {
            'meta':meta,
        }
    

    @PingService([ObjectS3Service])
    @UseHandler(S3Handler,FileNamingHandler)
    @UsePermission(AdminPermission)
    @UsePipe(ObjectS3OperationResponsePipe,before=False)
    @UsePipe(ValidFreeInputTemplatePipe(False,False),pipe_restore)
    @UseGuard(GlobalsTemplateGuard)
    @UseServiceLock(ObjectS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/copy/{template:path}/to/{destination_template:path}',methods=[HTTPMethod.PATCH],response_model=ObjectS3ResponseModel,mount=False)
    async def copy_object(self,template:str,request:Request,response:Response,destination_template:str,broker:Annotated[Broker,Depends(Broker)],objectsSearch:Annotated[ObjectsSearch,Depends(ObjectsSearch)],move:bool = Query(False),restore:bool = Query(False),authPermission:AuthPermission=Depends(get_auth_permission)):

        self.free_input_pipe.pipe(destination_template,objectsSearch)
        if objectsSearch.is_file:
            if self.fileService.get_extension(template) != self.fileService.get_extension(destination_template):
                raise ExtensionNotAllowedError('Extension of the destination_template should be the same as the template')    
        else:
            destination_template  = destination_template if destination_template.endswith('/') else destination_template+ "/" 
            destination_template += self.fileService.soft_get_filename(template)
        
        if template.split('/')[0] !=  destination_template.split('/')[0]:
            raise AssetTypeNotAllowedError
        
        broker.wait(3)
        broker.propagate_state(StateProtocol(service=AssetService,to_build=True,recursive=True,bypass_async_verify=False))

        return await self.objectS3Service.copy_object(template,destination_template,objectsSearch.version_id,move)

    
    ##################################################################################################################

    ##################################################################################################################

    @UsePermission(AdminPermission)
    @PingService([VaultService])
    @UseServiceLock(VaultService,lockType='reader',check_status=False)
    @UseGuard(is_minio_external_guard)
    @BaseHTTPRessource.HTTPRoute('/generate-url/',methods=[HTTPMethod.GET,HTTPMethod.PUT],mount=False)
    async def generate_url(self,request:Request,expiry:int=Query(3600,ge=6*60,le=HOUR*2),version:str=Query(None)): # type: ignore
        method = request.method
        url = await self.objectS3Service.generate_presigned_url(method=method,expiry=expiry,version_id=version)
        return {
            'presigned_url':url,
            'expiry':expiry,
            'method':method
        }
    

