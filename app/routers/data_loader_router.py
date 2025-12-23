from typing import TypedDict
from app.container import Get
from fastapi import APIRouter, Depends, HTTPException
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from app.services.file.file_service import FileService
import app.data_tasks
from arq.connections import RedisSettings,create_pool
from app.utils.constant import RedisConstant


class DataLoaderArqWorker:

    QUEUE_NAME = "data_loader_queue"

    def __init__(self):
        self.redisService = Get(RedisService)
        self.registered_tasks = []

    @property
    def arq_url(self):
        return f"redis://{self.redisService.db_user}:{self.redisService.db_password}@redis:6379/{RedisConstant.EVENT_DB}"

    async def initialize(self):
        redisSettings = RedisSettings.from_dsn(self.arq_url)
        self._worker = await create_pool(redisSettings)

    async def close(self):
        await self._worker.close()

    async def enqueue_task(self,task_name:str,_job_id:str=None,kwargs:dict={}):
        if task_name not in self.registered_tasks:
            raise HTTPException(status_code=400, detail=f"Task {task_name} is not registered.")
        await self._worker.enqueue_job(task_name,job_id=_job_id,_queue_name=self.QUEUE_NAME,**kwargs)
    
    async def get_queued_jobs(self,):
        return await self._worker.queued_jobs()
        
    async def get_jobs_results(self):
        return await self._worker.all_job_results()


def DataLoaderRouter(depends:list=None):
    prefix=''
    if depends == None:
        depends =[]

    configService = Get(ConfigService)
    redisService = Get(RedisService)
    fileService = Get(FileService)

    arqWorker = DataLoaderArqWorker()

    async def on_startup():
        await arqWorker.initialize()
    
    async def on_shutdown():
        await arqWorker.close()
    
    router = APIRouter(prefix=prefix,on_startup=[on_startup],on_shutdown=[on_shutdown])

    return router