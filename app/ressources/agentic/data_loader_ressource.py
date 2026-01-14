import asyncio
from random import random
from typing import Annotated, List
from fastapi import BackgroundTasks, Depends, File, Request, Response, UploadFile,status
from app.classes.auth_permission import AuthPermission, Role
from app.container import Get, InjectInMethod
from app.cost.file_cost import FileCost
from app.cost.web_cost import WebCost
from app.decorators.guards import ArqDataTaskGuard, LLMProviderGuard, UploadFilesGuard
from app.decorators.handlers import AgenticHandler, ArqHandler, AsyncIOHandler, CostHandler, FileHandler, MiniServiceHandler, PydanticHandler, ServiceAvailabilityHandler, UploadFileHandler, VaultHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.pipes import  DataClassToDictPipe, MerchantPipe, MiniServiceInjectorPipe, QueryToModelPipe, update_status_upon_no_metadata_pipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, IncludeRessource, PingService, Throttle, UseGuard, UseHandler, UseInterceptor, UsePermission, UsePipe, UseRoles, UseServiceLock
from app.definition._utils_decorator import Guard
from app.depends.class_dep import FileDataIngestQuery
from app.depends.dependencies import get_auth_permission, get_request_id
from app.depends.funcs_dep import get_profile
from app.manager.broker_manager import Broker
from app.manager.merchant_manager import Merchant
from app.services.config_service import ConfigService
from app.services.file.file_service import FileService
from app.services.profile_service import ProfileMiniService, ProfileService
from app.services.vault_service import VaultService
from app.decorators.permissions import JWTRouteHTTPPermission, ProfilePermission
from app.definition._ressource import UseLimiter
from app.services.worker.arq_service import ArqDataTaskService, JobAlreadyExistsError,JobStatus
from app.models.data_ingest_model import (
    AbortedJobResponse,
    IngestDataUriMetadata,
    EnqueueResponse,
    DataIngestModel,
    IngestFileEnqueueResponse,
    DataIngestFileModel,
)
from app.models.file_model import  FileResponseUploadModel, UploadError
from app.data_tasks import DATA_TASK_REGISTRY_NAME
from app.utils.constant import ArqDataTaskConstant, CostConstant
from app.utils.tools import RunInThreadPool



@UseHandler(ArqHandler,ServiceAvailabilityHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('jobs',)
class JobArqRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,configService:ConfigService,vaultService:VaultService,arqService:ArqDataTaskService,fileService:FileService):
        super().__init__(None,None)
        self.arqService = arqService
        self.configService = configService
        self.fileService = fileService
    
    @UseHandler(AsyncIOHandler)
    @PingService([ArqDataTaskService])
    @UseServiceLock(ArqDataTaskService,lockType='reader')
    @UsePipe(DataClassToDictPipe(),before=False)
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.GET])
    async def get_queued_jobs(self, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        return await self.arqService.get_queued_jobs()
        
    @UseHandler(AsyncIOHandler)
    @PingService([ArqDataTaskService])
    @UseServiceLock(ArqDataTaskService,lockType='reader')
    @UsePipe(DataClassToDictPipe(),before=False)
    @BaseHTTPRessource.HTTPRoute('/results/', methods=[HTTPMethod.GET])
    async def get_jobs_result(self, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        return await self.arqService.get_jobs_results()
        
    @UseHandler(AsyncIOHandler)    
    @PingService([ArqDataTaskService])
    @UseServiceLock(ArqDataTaskService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/info/{job_id}/', methods=[HTTPMethod.GET])
    async def get_job_info(self, job_id: str, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        job = await self.arqService.exists(job_id, raise_on_exist=False)
        info  = await self.arqService.info(job)
        return info

    @UseHandler(AsyncIOHandler)
    @PingService([ArqDataTaskService])
    @UseServiceLock(ArqDataTaskService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/result/{job_id}/', methods=[HTTPMethod.GET])
    async def get_job_result(self, job_id: str, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        job = await self.arqService.exists(job_id, raise_on_exist=False)
        result = await self.arqService.get_result(job)
        return result

    @UseLimiter('5/hour')
    @Throttle(uniform=(100,300))
    @PingService([ArqDataTaskService])
    @UseServiceLock(ArqDataTaskService,lockType='reader')
    @UseHandler(CostHandler,AsyncIOHandler,FileHandler)
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @BaseHTTPRessource.HTTPRoute('/{job_id}/', methods=[HTTPMethod.DELETE],response_model=AbortedJobResponse)
    async def abort_job(self, job_id: str, request: Request,response:Response,cost:Annotated[FileCost,Depends(FileCost)],broker:Annotated[Broker,Depends(Broker)],autPermission:AuthPermission=Depends(get_auth_permission)):
        job,status = await self.arqService.exists(job_id, raise_on_exist=False,return_status=True)

        match status:
            case JobStatus.queued | JobStatus.deferred:
                info = await self.arqService.info(job)
                await self.arqService.dequeue_task(job_id)

                if info.kwargs.get('_nickname',None) == ArqDataTaskConstant.FILE_DATA_TASK:
                    size,uri,sha = info.kwargs.get('size',0), info.kwargs.get('uri',None),info.kwargs.get('sha','unknown')
                    file_path = self.arqService.compute_data_file_upload_path(uri)
                    await RunInThreadPool(self.fileService.delete_file)(file_path)
                return AbortedJobResponse(aborted= True, metadata=[IngestDataUriMetadata(uri=uri,size=size,sha=sha)],status=status)
                
            case JobStatus.complete:
                return AbortedJobResponse(metadata=[],aborted=False,status=status)
            
            case JobStatus.in_progress:        
                result = await self.arqService.abort(job)
                return AbortedJobResponse(metadata=[],aborted=bool(result),status=status)
            
            case _:
                ...

@UseRoles([Role.ADMIN])
@PingService([ArqDataTaskService])
@IncludeRessource(JobArqRessource)
@UseHandler(ServiceAvailabilityHandler,CostHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('data-loader')
class DataLoaderRessource(BaseHTTPRessource):
    
    @staticmethod
    async def docling_guard(ingestTask:DataIngestFileModel):
        configService = Get(ConfigService)
        if not configService.INSTALL_DOCLING and ingestTask.use_docling:
            return False,"Docling is not installed"
        return True,""

    @InjectInMethod()
    def __init__(self,configService:ConfigService,vaultService:VaultService,fileService:FileService,arqService:ArqDataTaskService):
        super().__init__(None,None)
        self.configService = configService
        self.vaultService = vaultService
        self.fileService = fileService
        self.arqService = arqService

    @UseLimiter('10/hour')
    @Throttle(normal=(300,150))
    @UsePipe(QueryToModelPipe('ingestTask'),MerchantPipe)
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @UseServiceLock(ArqDataTaskService,lockType='reader')
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UseHandler(UploadFileHandler,ArqHandler,AsyncIOHandler,PydanticHandler,AgenticHandler)
    @UseGuard(ArqDataTaskGuard(ArqDataTaskConstant.FILE_DATA_TASK),LLMProviderGuard,UploadFilesGuard(),docling_guard)
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'purchase'))
    @BaseHTTPRessource.HTTPRoute('/file/',methods=[HTTPMethod.POST],response_model=IngestFileEnqueueResponse)
    async def embed_files(self,ingestTask:Annotated[DataIngestFileModel,Depends(lambda :None)], request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[FileCost,Depends(FileCost)],merchant:Annotated[Merchant,Depends(Merchant)],files:List[UploadFile]= File(...),request_id:str = Depends(get_request_id),query:FileDataIngestQuery = Depends(FileDataIngestQuery), autPermission:AuthPermission=Depends(get_auth_permission)):
        _response = IngestFileEnqueueResponse()
        ingest_sha = set()
        for file in files:
            try:
                uri= file.filename.lower()
                file_path = self.arqService.compute_data_file_upload_path(uri)
                sha = await self.fileService.compute_sha256(file.file)

                if sha in ingest_sha:
                    raise JobAlreadyExistsError(uri,'file already added')
                
                ingest_sha.add(sha)

                await self.arqService.exists(uri, True,True)
                await self.arqService.search(ArqDataTaskConstant.FILE_DATA_TASK,{'sha':sha},True)
                await self.fileService.download_file(file_path, await file.read())

                meta = IngestDataUriMetadata(uri=uri, size=file.size,sha=sha)
                _response.metadata.append(meta)

                merchant.safe_payment(
                    None,
                    FileResponseUploadModel(metadata=[meta]),
                    self.arqService.enqueue_task,ArqDataTaskConstant.FILE_DATA_TASK,
                    job_id=uri,
                    expires=ingestTask.expires,
                    defer_by=ingestTask.defer_by,
                    kwargs={**ingestTask.model_dump(mode='json',exclude=('expires','defer_by')),
                            **meta.model_dump(),
                            'request_id':request_id,
                            '_nickname':ArqDataTaskConstant.FILE_DATA_TASK,
                            'step':None
                            }
                )
            except JobAlreadyExistsError as e:
                _response.errors[uri] = UploadError(reason=e.reason,file_path=file_path)
            except OSError as e:
                _response.errors[uri] = UploadError(reason = str(e),file_path=file_path)
        
        return _response

    @UseLimiter('5/hour')
    @Throttle(normal=(300,150))
    @UsePipe(MerchantPipe())
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @UseHandler(ArqHandler,AsyncIOHandler,AgenticHandler)
    @UseGuard(ArqDataTaskGuard(ArqDataTaskConstant.WEB_DATA_TASK),LLMProviderGuard)
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'purchase'))
    @UseServiceLock(ArqDataTaskService,lockType='reader')
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @BaseHTTPRessource.HTTPRoute('/web/',methods=[HTTPMethod.POST],response_model=EnqueueResponse,mount=False)
    async def embed_web(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[WebCost,Depends(WebCost)],merchant:Annotated[Merchant,Depends(Merchant)],request_id:str = Depends(get_request_id),autPermission:AuthPermission=Depends(get_auth_permission)):
        """
        Accepts a JSON body describing a `WebCrawlTask` and enqueues it.
        """
    
    @UseLimiter('5/hour')
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @UsePermission(ProfilePermission)
    @Throttle(normal=(300,150))
    @UsePipe(MerchantPipe())
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UseGuard(ArqDataTaskGuard(ArqDataTaskConstant.API_DATA_TASK),LLMProviderGuard)
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'purchase'))
    @UseHandler(ArqHandler,AsyncIOHandler,MiniServiceHandler,VaultHandler,AgenticHandler)
    @UsePipe(MiniServiceInjectorPipe(ProfileService))
    @UseServiceLock(ArqDataTaskService,ProfileService,lockType='reader',as_manager=True)
    @BaseHTTPRessource.HTTPRoute('/api/{profile}',methods=[HTTPMethod.POST],response_model=EnqueueResponse,mount=False)
    async def embed_api_data(self,profile:Annotated[ProfileMiniService,Depends(get_profile)],request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],merchant:Annotated[Merchant,Depends(Merchant)],cost:Annotated[WebCost,Depends(WebCost)],request_id:str = Depends(get_request_id),authPermission:AuthPermission=Depends(get_auth_permission)):
        """
        Accepts a JSON body describing an `APIFetchTask` and enqueues it.
        """

    async def on_startup(self):
        self.arqService.register_task(DATA_TASK_REGISTRY_NAME)
        await self.arqService.initialize()
    
    async def on_shutdown(self):
        await self.arqService.close()

