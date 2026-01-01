from typing import Annotated, List
from fastapi import BackgroundTasks, Depends, Request, Response, UploadFile
from app.classes.auth_permission import AuthPermission, Role
from app.container import Get, InjectInMethod
from app.cost.file_cost import FileCost
from app.decorators.guards import UploadFilesGuard
from app.decorators.handlers import ArqHandler, CostHandler, ServiceAvailabilityHandler, UploadFileHandler
from app.decorators.interceptors import DataCostInterceptor
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, IncludeRessource, UseGuard, UseHandler, UseInterceptor, UsePermission, UseRoles
from app.depends.dependencies import get_auth_permission
from app.services.config_service import ConfigService
from app.services.file.file_service import FileService
from app.services.vault_service import VaultService
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import UseLimiter
from app.services.worker.arq_service import ArqService, JobDoesNotExistsError
from app.models.data_task_model import (
    FileIngestTask,
    EnqueueResponse,
)
from fastapi import HTTPException, status
from app.data_tasks import DATA_TASK_REGISTRY


@UseHandler(ArqHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('jobs',)
class JobArqRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,configService:ConfigService,vaultService:VaultService,arqService:ArqService):
        super().__init__(None,None)
        self.arqService = arqService
    

    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.GET])
    async def get_queued_jobs(self, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        queued = await self.arqService.get_queued_jobs()
        return {"count": len(queued), "queued": queued}

    @BaseHTTPRessource.HTTPRoute('/results/', methods=[HTTPMethod.GET])
    async def get_jobs_result(self, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        results = await self.arqService.get_jobs_results()
        return {"count": len(results), "results": results}

    @BaseHTTPRessource.HTTPRoute('/{job_id}/', methods=[HTTPMethod.GET])
    async def get_job_info(self, job_id: str, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        await self.arqService.job_exists(job_id, raise_on_exist=False)
        job = await self.arqService.fetch_job(job_id)
        return {"job_id": job_id, "repr": str(job)}

    @BaseHTTPRessource.HTTPRoute('/{job_id}/result/', methods=[HTTPMethod.GET])
    async def get_job_result(self, job_id: str, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        await self.arqService.job_exists(job_id, raise_on_exist=False)
        results = await self.arqService.get_jobs_results()
        for r in results:
            if r.get('job_id') == job_id or r.get('id') == job_id:
                return r
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job result {job_id} not found")

    @BaseHTTPRessource.HTTPRoute('/{job_id}/abort/', methods=[HTTPMethod.POST])
    async def abort_job(self, job_id: str, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        await self.arqService.job_exists(job_id, raise_on_exist=False)
        result = await self.arqService.abort_job(job_id)
        return {"job_id": job_id, "aborted": bool(result)}


@IncludeRessource(JobArqRessource)
@UseHandler(ServiceAvailabilityHandler,CostHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('data-loader')
class DataLoaderRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,configService:ConfigService,vaultService:VaultService,fileService:FileService,arqService:ArqService):
        super().__init__(None,None)
        self.configService = configService
        self.vaultService = vaultService
        self.fileService = fileService
        self.arqService = arqService

    async def on_startup(self):
        self.arqService.register_task(DATA_TASK_REGISTRY)
        await self.arqService.initialize()
    
    async def on_shutdown(self):
        await self.arqService.close()

    @UseLimiter('5/hour')
    @UseRoles([Role.ADMIN])
    @UseHandler(UploadFileHandler,ArqHandler)
    @UseGuard(UploadFilesGuard())
    @UseInterceptor(DataCostInterceptor('documents','purchase'))
    @BaseHTTPRessource.HTTPRoute('/file/',methods=[HTTPMethod.POST],response_model=EnqueueResponse)
    async def embed_files(self,files:List[UploadFile],fileTask:FileIngestTask, request:Request,response:Response,cost:Annotated[FileCost,Depends(FileCost)],backgroundTasks:BackgroundTasks,autPermission:AuthPermission=Depends(get_auth_permission)):
        """ """
        jobs_ids = []
        errors = {}
        meta = []
        for f in files:
            try:
                
                job_id = f"arq:{f.filename}"
                await self.arqService.job_exists(job_id,True)
                tmp_name = await self.fileService.download_temp_file(f.filename,await f.read())
                fileTask._file_path = tmp_name
                jobs_ids.append(job_id)
                meta.append((f.filename,f.size))
                backgroundTasks.add_task(self.arqService.enqueue_task,'process_file_loader_task', _job_id=job_id, kwargs=fileTask.model_dump())
            except JobDoesNotExistsError as e:
                errors[e.job_id] = {'reason':e.reason}

        return EnqueueResponse(jobs_ids=jobs_ids,errors=errors,meta=meta).model_dump()

    @UseLimiter('5/hour')
    @UseHandler(ArqHandler)
    @BaseHTTPRessource.HTTPRoute('/web/',methods=[HTTPMethod.POST],response_model=EnqueueResponse)
    async def embed_web(self,request:Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        """
        Accepts a JSON body describing a `WebCrawlTask` and enqueues it.
        """
    
    @UseLimiter('5/hour')
    @UseHandler(ArqHandler)
    @BaseHTTPRessource.HTTPRoute('/api/',methods=[HTTPMethod.POST],response_model=List[EnqueueResponse])
    async def embed_api_data(self,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        """
        Accepts a JSON body describing an `APIFetchTask` and enqueues it.
        """

    