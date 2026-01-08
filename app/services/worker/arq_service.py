import asyncio
from datetime import timedelta
from typing import Any, Callable, Literal, Union
from arq.connections import RedisSettings,create_pool,ArqRedis
from arq.jobs import Job,JobStatus,ResultNotFound,JobResult,JobDef
from arq.constants import result_key_prefix,job_key_prefix
from app.definition._error import BaseError
from app.definition._service import BaseService, Service
from app.services.config_service import ConfigService, UvicornWorkerService
from app.services.file.file_service import FileService
from app.utils.constant import RedisConstant
from app.services.database.redis_service import RedisService
from app.utils.globals import APP_MODE,ApplicationMode

Time = Union[int | float | timedelta | None]
QUEUE_NAME = 'arq:data_loader_task'

class DataTaskNotFoundError(BaseError):
    def __init__(self, job_id:str,reason:str):
        super().__init__(job_id,reason)
        self.job_id = job_id
        self.reason = reason

class JobDoesNotExistsError(BaseError):
    def __init__(self, job_id:str,reason:str):
        super().__init__()
        self.job_id = job_id
        self.reason = reason

class JobAlreadyExistsError(BaseError):
    def __init__(self, job_id:str,reason:str):
        super().__init__()
        self.job_id = job_id
        self.reason = reason

class JobStatusNotValidError(BaseError): 

    def __init__(self,job_id:str, status:str):
        super().__init__()
        self.job_id = job_id
        self.status = status

class JobDequeueError(BaseError):
    def __init__(self, job_id:str):
        self.job_id= job_id

@Service()
class ArqDataTaskService(BaseService):

    def build(self, build_state = ...):
        if APP_MODE == ApplicationMode.server or APP_MODE == ApplicationMode.arq:
            #self.arq_url = self.redisService.compute_backend_url(RedisConstant.EVENT_DB)
            user,password = self.redisService.db_user,self.redisService.db_password
            host = self.configService.REDIS_HOST
            self.arq_url = f"redis://{user}:{password}@redis:6379/{RedisConstant.EVENT_DB}"

    def __init__(self,redisService:RedisService,configService:ConfigService,UvicornWorkerService:UvicornWorkerService):
        self.redisService = redisService
        self.configService = configService
        self.uvicornWorkerService = UvicornWorkerService      
        super().__init__()  

    if APP_MODE == ApplicationMode.server or APP_MODE == ApplicationMode.arq:
        def register_task(self,tasks:dict[str,str]):
            self.task_registry = tasks

        async def initialize(self):
            redisSettings = RedisSettings.from_dsn(self.arq_url)
            self._worker = await create_pool(redisSettings)

        async def close(self):
            await self._worker.close()

        async def enqueue_task(self,task_name:str,job_id:str=None,expires:Time=None,defer_by:Time = None,kwargs:dict={}):
            task_name = self.task_registry[task_name]
            task = await self._worker.enqueue_job(task_name,_job_id=job_id,_queue_name=QUEUE_NAME,_expires=expires,_defer_by=defer_by, **kwargs)
            return task
        
        async def get_queued_jobs(self)->list[JobDef]:
            return await self._worker.queued_jobs(queue_name=QUEUE_NAME) or []
            
        async def get_jobs_results(self)->list[JobDef]:
            return await self._worker.all_job_results() or []
        
        async def fetch(self,job_id:str):
            return Job(job_id,self._worker,QUEUE_NAME)
        
        async def info(self,job_id:str|Job):
            if isinstance(job_id,str):
                job_id = await self.fetch(job_id)
            
            return await job_id.info()
        
        async def abort(self,job_id:str|Job)->bool:
            if isinstance(job_id,str):
                job_id = await self.fetch(job_id)
            try:
                return await job_id.abort(timeout=0.5)
            except asyncio.TimeoutError:
                return False
        
        async def dequeue_task(self,job_id:str):
            val = await self.redisService.rem(RedisConstant.EVENT_DB,QUEUE_NAME,job_id)
            print(val)
            job_key = job_key_prefix+job_id
            await self.redisService.delete(RedisConstant.EVENT_DB,job_key)
            return

        async def get_result(self,job_id:str|Job,_raise=True):
            if isinstance(job_id,str):
                job_id = await self.fetch(job_id)
            
            info = await job_id.result_info()
            if info == None and _raise:
                raise ResultNotFound
            return info
        
        async def status(self,job_id:str|Job):
            if isinstance(job_id,str):
                job_id = await self.fetch(job_id)

            return await job_id.status()
    
        async def search(self,task:str,params:dict,_raise:bool|None)->Job|BaseError|None:
            task = self.task_registry[task]
            for job in [*await self.get_queued_jobs(), *await self.get_jobs_results()]:
                for k,v in params.items():
                    if k in job.kwargs and job.kwargs[k] == v:
                        if _raise != None and _raise:
                            raise JobAlreadyExistsError(job.job_id,f'job exist found with the search params: {params}')
                        else:
                            return job
            if _raise != None and not _raise:
                raise JobDoesNotExistsError('not specified',f'job does not exist found with the search params: {params}')
            return None

        async def filter(self,task:str,params:Any,where:str):
            ...
            
        async def exists(self,job_id:str,raise_on_exist=False,delete_on_error:bool=False):
            job = await self.fetch(job_id)
            status:JobStatus = await job.status()
                        
            match status:
                case JobStatus.not_found:
                    if not raise_on_exist:
                        raise JobDoesNotExistsError(job_id,'does not exists')
                case JobStatus.complete:
                    if delete_on_error:
                        result:JobResult = await job.result_info()
                        if result and not result.success:
                            await self.delete_result(job_id)
                    if not raise_on_exist:
                        raise JobDoesNotExistsError(job_id,'job as been completed')
                
                case JobStatus.in_progress | JobStatus.queued | JobStatus.deferred:
                    if raise_on_exist:
                        raise JobAlreadyExistsError(job_id,'job already exists')

            return job
        
        async def delete_result(self, job_id: str ) -> bool:
            result_key = f"{result_key_prefix}{job_id}"
            return await self.redisService.delete(RedisConstant.EVENT_DB,result_key)
       
    def compute_data_file_upload_path(self,filename:str):
        return f"{self.configService.DATA_LOADER_DIR}uploads/{filename}"
    