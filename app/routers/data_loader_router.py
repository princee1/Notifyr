from typing import List, TypedDict
from app.classes.arq_worker import ArqWorker,Job
from app.container import Get
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile,status
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from app.services.file.file_service import FileService
from app.data_tasks import DATA_TASK_REGISTRY
from app.utils.constant import RedisConstant

QUEUE_NAME = 'arq:data_loader'

def JobRouter(arqWorker:ArqWorker):
        
    router = APIRouter(prefix='/jobs')

    async def get_queued_jobs(self):
        ...
    
    async def get_jobs_result(self):
        ...
    
    async def get_job_info(self):
        ...
    
    async def get_job_result(self):
        ...
    
    async def abort_job(self):
        ...
        
    return router


def DataLoaderRouter(depends:list=None):
    prefix='/data-loader'
    if depends == None:
        depends =[]

    configService = Get(ConfigService)
    redisService = Get(RedisService)
    fileService = Get(FileService)

    dataLoaderWorker = ArqWorker(
        f"redis://{redisService.db_user}:{redisService.db_password}@redis:6379/{RedisConstant.EVENT_DB}",
        DATA_TASK_REGISTRY,
        QUEUE_NAME)

    async def on_startup():
        await dataLoaderWorker.initialize()
    
    async def on_shutdown():
        await dataLoaderWorker.close()
    
    router = APIRouter(prefix=prefix,on_startup=[on_startup],on_shutdown=[on_shutdown])
    
    router.include_router(JobRouter(dataLoaderWorker))

    
    router.post('/text/',status_code=status.HTTP_202_ACCEPTED)
    async def embed_text(request:Request,response:Response,files:List[UploadFile]):
        ...
    
    router.post('/web/',status_code=status.HTTP_202_ACCEPTED)
    async def embed_web_research(request:Request,response:Response):
        ...
    
    router.post('/api/',status_code=status.HTTP_202_ACCEPTED)
    async def embed_api(request:Request,response:Response,files:List[UploadFile]):
        ...

            
    return router