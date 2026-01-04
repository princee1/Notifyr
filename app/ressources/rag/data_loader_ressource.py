import asyncio
from typing import Annotated, List
from fastapi import BackgroundTasks, Depends, Request, Response, UploadFile
from app.classes.auth_permission import AuthPermission, Role
from app.container import Get, InjectInMethod
from app.cost.file_cost import FileCost
from app.cost.web_cost import WebCost
from app.decorators.guards import ArqDataTaskGuard, UploadFilesGuard
from app.decorators.handlers import ArqHandler, AsyncIOHandler, CostHandler, ServiceAvailabilityHandler, UploadFileHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.pipes import ArqJobIdPipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, IncludeRessource, PingService, UseGuard, UseHandler, UseInterceptor, UsePermission, UsePipe, UseRoles, UseServiceLock
from app.depends.dependencies import get_auth_permission
from app.services.config_service import ConfigService
from app.services.file.file_service import FileService
from app.services.vault_service import VaultService
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import UseLimiter
from app.services.worker.arq_service import ArqDataTaskService, JobDoesNotExistsError
from app.models.data_task_model import (
    AbortedJobResponse,
    EnqueueResponse,
    DataIngestTask,
    DataEnqueueResponse,
)
from app.models.file_model import UriMetadata, UploadError
from app.data_tasks import task_registry, DATA_TASK_REGISTRY_NAME
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
        self.fileGuard = ArqDataTaskGuard(ArqDataTaskConstant.FILE_DATA_TASK)
    
    @UseHandler(AsyncIOHandler)
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.GET])
    async def get_queued_jobs(self, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        queued = await self.arqService.get_queued_jobs()
        return {"count": len(queued), "queued": queued}

    @UseHandler(AsyncIOHandler)
    @BaseHTTPRessource.HTTPRoute('/results/', methods=[HTTPMethod.GET])
    async def get_jobs_result(self, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        results = await self.arqService.get_jobs_results()
        return {"count": len(results), "results": results}

    @UseHandler(AsyncIOHandler)
    @UsePipe(ArqJobIdPipe)
    @BaseHTTPRessource.HTTPRoute('/{job_id}/', methods=[HTTPMethod.GET])
    async def get_job_info(self, job_id: str, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        job = await self.arqService.job_exists(job_id, raise_on_exist=False)
        info  = await self.arqService.job_info(job)
        return info

    @UseHandler(AsyncIOHandler)
    @UsePipe(ArqJobIdPipe)
    @BaseHTTPRessource.HTTPRoute('/{job_id}/result/', methods=[HTTPMethod.GET])
    async def get_job_result(self, job_id: str, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        job = await self.arqService.job_exists(job_id, raise_on_exist=False)
        result = await self.arqService.job_results(job)
        return result
        
    @UseHandler(CostHandler,AsyncIOHandler)
    @UsePipe(ArqJobIdPipe)
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @BaseHTTPRessource.HTTPRoute('/{job_id}/', methods=[HTTPMethod.DELETE],response_model=AbortedJobResponse)
    async def abort_job(self, job_id: str, request: Request,response:Response,cost:Annotated[FileCost,Depends(FileCost)],autPermission:AuthPermission=Depends(get_auth_permission)):
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

    @InjectInMethod()
    def __init__(self,configService:ConfigService,vaultService:VaultService,fileService:FileService,arqService:ArqDataTaskService):
        super().__init__(None,None)
        self.configService = configService
        self.vaultService = vaultService
        self.fileService = fileService
        self.arqService = arqService

    async def on_startup(self):
        self.arqService.register_task(DATA_TASK_REGISTRY_NAME)
        await self.arqService.initialize()
    
    async def on_shutdown(self):
        await self.arqService.close()

    @UseLimiter('5/hour')
    @UseHandler(UploadFileHandler,ArqHandler,AsyncIOHandler)
    @UseGuard(ArqDataTaskGuard(ArqDataTaskConstant.FILE_DATA_TASK),UploadFilesGuard())
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'purchase'))
    @UseServiceLock(ArqDataTaskService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/file/',methods=[HTTPMethod.POST],response_model=DataEnqueueResponse)
    async def embed_files(self,files:List[UploadFile],ingestTask:DataIngestTask, request:Request,response:Response,cost:Annotated[FileCost,Depends(FileCost)],backgroundTasks:BackgroundTasks,autPermission:AuthPermission=Depends(get_auth_permission)):
        response_data = DataEnqueueResponse()
        
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
                    kwargs={**ingestTask.model_dump(exclude=('expires','defer_by')),**meta.model_dump()}
                )
            except JobDoesNotExistsError as e:
                response_data.errors[file.filename] = UploadError(reason=e.reason)
            except OSError as e:
                response_data.errors[file.filename] = UploadError(reason = str(e))
        
        return response_data

    @UseLimiter('5/hour')
    @UseHandler(ArqHandler,AsyncIOHandler)
    @UseGuard(ArqDataTaskGuard(ArqDataTaskConstant.WEB_DATA_TASK))
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'purchase'))
    @UseServiceLock(ArqDataTaskService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/web/',methods=[HTTPMethod.POST],response_model=EnqueueResponse)
    async def embed_web(self,request:Request,response:Response,cost:Annotated[WebCost,Depends(WebCost)],autPermission:AuthPermission=Depends(get_auth_permission)):
        """
        Accepts a JSON body describing a `WebCrawlTask` and enqueues it.
        """
    
    @UseLimiter('5/hour')
    @UseGuard(ArqDataTaskGuard(ArqDataTaskConstant.API_DATA_TASK))
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'purchase'))
    @UseHandler(ArqHandler,AsyncIOHandler)
    @UseServiceLock(ArqDataTaskService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/api/',methods=[HTTPMethod.POST],response_model=EnqueueResponse)
    async def embed_api_data(self,request:Request,response:Response,cost:Annotated[WebCost,Depends(WebCost)],authPermission:AuthPermission=Depends(get_auth_permission)):
        """
        Accepts a JSON body describing an `APIFetchTask` and enqueues it.
        """

    