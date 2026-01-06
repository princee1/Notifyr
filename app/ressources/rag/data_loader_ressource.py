import asyncio
from typing import Annotated, List
from fastapi import BackgroundTasks, Depends, Request, Response, UploadFile,status
from app.classes.auth_permission import AuthPermission, Role
from app.container import Get, InjectInMethod
from app.cost.file_cost import FileCost
from app.cost.web_cost import WebCost
from app.decorators.guards import ArqDataTaskGuard, UploadFilesGuard
from app.decorators.handlers import ArqHandler, AsyncIOHandler, CostHandler, MiniServiceHandler, ServiceAvailabilityHandler, UploadFileHandler, VaultHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.pipes import ArqJobIdPipe, DataClassToDictPipe, MiniServiceInjectorPipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, IncludeRessource, PingService, UseGuard, UseHandler, UseInterceptor, UsePermission, UsePipe, UseRoles, UseServiceLock
from app.depends.dependencies import get_auth_permission
from app.depends.funcs_dep import get_profile
from app.manager.broker_manager import Broker
from app.services.config_service import ConfigService
from app.services.file.file_service import FileService
from app.services.profile_service import ProfileMiniService, ProfileService
from app.services.vault_service import VaultService
from app.decorators.permissions import JWTRouteHTTPPermission, ProfilePermission
from app.definition._ressource import UseLimiter
from app.services.worker.arq_service import ArqDataTaskService, JobDoesNotExistsError
from app.models.data_ingest_model import (
    AbortedJobResponse,
    EnqueueResponse,
    DataIngestTask,
    FileDataEnqueueResponse,
    FileDataIngestTask,
)
from app.models.file_model import UriMetadata, UploadError
from app.data_tasks import DATA_TASK_REGISTRY_NAME
from app.utils.constant import ArqDataTaskConstant, CostConstant


@UseHandler(ArqHandler,ServiceAvailabilityHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('jobs',)
class JobArqRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,configService:ConfigService,vaultService:VaultService,arqService:ArqDataTaskService):
        super().__init__(None,None)
        self.arqService = arqService
        self.configService = configService
    
    @UseHandler(AsyncIOHandler)
    @UsePipe(DataClassToDictPipe(),before=False)
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.GET])
    async def get_queued_jobs(self, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        return await self.arqService.get_queued_jobs()
        
    @UseHandler(AsyncIOHandler)
    @UsePipe(DataClassToDictPipe(),before=False)
    @BaseHTTPRessource.HTTPRoute('/results/', methods=[HTTPMethod.GET])
    async def get_jobs_result(self, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        return await self.arqService.get_jobs_results()
        
    @UseHandler(AsyncIOHandler)
    @UsePipe(ArqJobIdPipe)
    @BaseHTTPRessource.HTTPRoute('/{job_id}/', methods=[HTTPMethod.GET])
    async def get_job_info(self, job_id: str, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        job = await self.arqService.job_exists(job_id, raise_on_exist=False)
        info  = await self.arqService.job_info(job)
        return info

    @UseHandler(AsyncIOHandler)
    @UsePipe(ArqJobIdPipe)
    @BaseHTTPRessource.HTTPRoute('/result/{job_id}/', methods=[HTTPMethod.GET])
    async def get_job_result(self, job_id: str, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        job = await self.arqService.job_exists(job_id, raise_on_exist=False)
        result = await self.arqService.job_results(job)
        return result
        
    @UseHandler(CostHandler,AsyncIOHandler)
    @UsePipe(ArqJobIdPipe)
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @BaseHTTPRessource.HTTPRoute('/{job_id}/', methods=[HTTPMethod.DELETE],response_model=AbortedJobResponse)
    async def abort_job(self, job_id: str, request: Request,response:Response,cost:Annotated[FileCost,Depends(FileCost)],broker:Annotated[Broker,Depends(Broker)],autPermission:AuthPermission=Depends(get_auth_permission)):
        job = await self.arqService.job_exists(job_id, raise_on_exist=False)

        result = await self.arqService.abort_job(job)
        info = await self.arqService.job_info(job)
        state = await self.arqService.state_after_abort(job)
       
        if ArqDataTaskConstant.FILE_DATA_TASK in DATA_TASK_REGISTRY_NAME and  info.function == DATA_TASK_REGISTRY_NAME[ArqDataTaskConstant.FILE_DATA_TASK]:
            if state == 'deleted':
                size,filename = info.kwargs('size',None), info.kwargs('filename',None)
                return AbortedJobResponse(aborted= True, meta=[UriMetadata(uri=filename,size=size)],state=state)
            else:
                await asyncio.sleep(1.5)
                await self.arqService.delete_job_result(job_id)
                return AbortedJobResponse(metadata=[],aborted=True,state=state)
           
        return AbortedJobResponse(metadata=[],aborted=bool(result),state=state)



@UseRoles([Role.ADMIN])
@PingService([ArqDataTaskService])
@IncludeRessource(JobArqRessource)
@UseHandler(ServiceAvailabilityHandler,CostHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('data-loader')
class DataLoaderRessource(BaseHTTPRessource):

    @staticmethod
    async def inject_request_id(ingestTask:DataIngestTask,request_id:str):
        ingestTask._request_id = request_id
        return {}
    
    @staticmethod
    async def docling_guard(ingestTask:FileDataIngestTask):
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

    @UseLimiter('5/hour')
    @UsePipe(inject_request_id)
    @UseServiceLock(ArqDataTaskService,lockType='reader')
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UseHandler(UploadFileHandler,ArqHandler,AsyncIOHandler)
    @UseGuard(ArqDataTaskGuard(ArqDataTaskConstant.FILE_DATA_TASK),UploadFilesGuard(),docling_guard)
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'purchase'))
    @BaseHTTPRessource.HTTPRoute('/file/',methods=[HTTPMethod.POST],response_model=FileDataEnqueueResponse)
    async def embed_files(self,files:List[UploadFile],ingestTask:FileDataIngestTask, request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[FileCost,Depends(FileCost)],backgroundTasks:BackgroundTasks,autPermission:AuthPermission=Depends(get_auth_permission)):
        response_data = FileDataEnqueueResponse()
        
        for file in files:
            try:
                job_id = self.arqService.compute_job_id(file.filename)
                file_path = self.arqService.compute_data_file_task_path(file.filename)

                await self.arqService.job_exists(job_id, True,True)
                await self.fileService.download_file(file_path, await file.read())

                meta = UriMetadata(uri=file.filename, size=file.size)
                response_data.metadata.append(meta)
                backgroundTasks.add_task(self.arqService.enqueue_task,ArqDataTaskConstant.FILE_DATA_TASK,
                    job_id=job_id,expires=ingestTask.expires,defer_by=ingestTask.defer_by,
                    kwargs={**ingestTask.model_dump(mode='json',exclude=('expires','defer_by')),**meta.model_dump()}
                )
            except JobDoesNotExistsError as e:
                response_data.errors[file.filename] = UploadError(reason=e.reason)
            except OSError as e:
                response_data.errors[file.filename] = UploadError(reason = str(e))
        
        return response_data

    @UseLimiter('5/hour')
    @UsePipe(inject_request_id)
    @UseHandler(ArqHandler,AsyncIOHandler)
    @UseGuard(ArqDataTaskGuard(ArqDataTaskConstant.WEB_DATA_TASK))
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'purchase'))
    @UseServiceLock(ArqDataTaskService,lockType='reader')
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @BaseHTTPRessource.HTTPRoute('/web/',methods=[HTTPMethod.POST],response_model=EnqueueResponse,mount=False)
    async def embed_web(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[WebCost,Depends(WebCost)],autPermission:AuthPermission=Depends(get_auth_permission)):
        """
        Accepts a JSON body describing a `WebCrawlTask` and enqueues it.
        """
    
    @UseLimiter('5/hour')
    @UsePipe(inject_request_id)
    @UsePermission(ProfilePermission)
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UseGuard(ArqDataTaskGuard(ArqDataTaskConstant.API_DATA_TASK))
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'purchase'))
    @UseHandler(ArqHandler,AsyncIOHandler,MiniServiceHandler,VaultHandler)
    @UsePipe(MiniServiceInjectorPipe(ProfileService))
    @UseServiceLock(ArqDataTaskService,ProfileService,lockType='reader',as_manager=True)
    @BaseHTTPRessource.HTTPRoute('/api/{profile}',methods=[HTTPMethod.POST],response_model=EnqueueResponse,mount=False)
    async def embed_api_data(self,profile:Annotated[ProfileMiniService,Depends(get_profile)],request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[WebCost,Depends(WebCost)],authPermission:AuthPermission=Depends(get_auth_permission)):
        """
        Accepts a JSON body describing an `APIFetchTask` and enqueues it.
        """

    async def on_startup(self):
        self.arqService.register_task(DATA_TASK_REGISTRY_NAME)
        await self.arqService.initialize()
    
    async def on_shutdown(self):
        await self.arqService.close()