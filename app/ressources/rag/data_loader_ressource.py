from typing import List
from fastapi import Depends, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from app.classes.auth_permission import AuthPermission
from app.container import Get, InjectInMethod
from app.data_tasks import DATA_TASK_REGISTRY
from app.decorators.guards import UploadFilesGuard
from app.decorators.handlers import CostHandler, ServiceAvailabilityHandler, UploadFileHandler
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, IncludeRessource, UseGuard, UseHandler, UsePermission
from app.depends.dependencies import get_auth_permission
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from app.services.file.file_service import FileService
from app.services.vault_service import VaultService
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import UseLimiter
from app.classes.arq_worker import ArqWorker, DataTaskNotFoundError, JobDoesNotExistsError
from app.utils.constant import RedisConstant
from app.models.data_task_model import (
    FileIngestTask,
    WebCrawlTask,
    APIFetchTask,
    EnqueueResponse,
    JobInfo,
)
from typing import Dict, Any
from fastapi import HTTPException
import tempfile
import uuid
import os

QUEUE_NAME = 'arq:data_loader_task'
redisService= Get(RedisService)
dataLoaderWorker = ArqWorker(redisService.db_user,redisService.db_password,DATA_TASK_REGISTRY,QUEUE_NAME)

@HTTPRessource('jobs',)
class JobArqRessource(BaseHTTPRessource):
    
    @InjectInMethod()
    def __init__(self,configService:ConfigService,vaultService:VaultService):
        super().__init__(None,None)
    
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.GET])
    async def get_queued_jobs(self, request: Request):
        queued = await dataLoaderWorker.get_queued_jobs()
        return {"count": len(queued), "queued": queued}

    @BaseHTTPRessource.HTTPRoute('/results/', methods=[HTTPMethod.GET])
    async def get_jobs_result(self, request: Request):
        results = await dataLoaderWorker.get_jobs_results()
        return {"count": len(results), "results": results}

    @BaseHTTPRessource.HTTPRoute('/{job_id}/', methods=[HTTPMethod.GET])
    async def get_job_info(self, job_id: str):
        job = await dataLoaderWorker.fetch_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        return {"job_id": job_id, "repr": str(job)}

    @BaseHTTPRessource.HTTPRoute('/{job_id}/result/', methods=[HTTPMethod.GET])
    async def get_job_result(self, job_id: str):
        results = await dataLoaderWorker.get_jobs_results()
        for r in results:
            if r.get('job_id') == job_id or r.get('id') == job_id:
                return r
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    @BaseHTTPRessource.HTTPRoute('/{job_id}/abort/', methods=[HTTPMethod.POST])
    async def abort_job(self, job_id: str):
        # abort not implemented on ArqWorker
        raise HTTPException(status_code=501, detail='Abort not implemented for arq worker')


@IncludeRessource(JobArqRessource)
@UseHandler(ServiceAvailabilityHandler,CostHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('data-loader')
class DataLoaderRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,configService:ConfigService,vaultService:VaultService,fileService:FileService):
        super().__init__(None,None)
        self.configService = configService
        self.vaultService = vaultService
        self.fileService = fileService

    async def on_startup():
        await dataLoaderWorker.initialize()
    
    async def on_shutdown():
        await dataLoaderWorker.close()

    @UseLimiter('5/hour')
    @UseHandler(UploadFileHandler)
    @UseGuard(UploadFilesGuard())
    @BaseHTTPRessource.HTTPRoute('/file/',methods=[HTTPMethod.POST],response_model=EnqueueResponse)
    async def embed_files(self,files:List[UploadFile],fileTask:FileIngestTask, request:Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        """
        1. iterate over each files
        2. save uploaded file to a temporary path (workers should be able to access it)
        3. enqueue jobs with `FileIngestTask` kwargs
        4. return the response with enqueued job ids
        """
        jobs_ids = []
        errors = {}
        for f in files:
            try:
                job_id = f"arq:{f.filename}"
                await dataLoaderWorker.job_exists(job_id,True)
                tmp_name = await self.fileService.download_temp_file(f.filename,await f.read())
                fileTask._file_path = tmp_name
                await dataLoaderWorker.enqueue_task('process_file_loader_task', _job_id=job_id, kwargs=fileTask.model_dump())
                jobs_ids.append(job_id)
            except JobDoesNotExistsError as e:
                errors[e.job_id] = {'reason':e.reason}
        
        return EnqueueResponse(_jobs_ids=jobs_ids,_errors=errors).model_dump()


    @UseLimiter('5/hour')
    @BaseHTTPRessource.HTTPRoute('/web/',methods=[HTTPMethod.POST],response_model=EnqueueResponse)
    async def embed_web(self,request:Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        """
        Accepts a JSON body describing a `WebCrawlTask` and enqueues it.
        """
    
    @UseLimiter('5/hour')
    @BaseHTTPRessource.HTTPRoute('/api/',methods=[HTTPMethod.POST],response_model=List[EnqueueResponse])
    async def embed_api_data(self,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        """
        Accepts a JSON body describing an `APIFetchTask` and enqueues it.
        """

    