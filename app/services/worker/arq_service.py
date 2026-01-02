from typing import Callable, Literal
from arq.connections import RedisSettings,create_pool,ArqRedis
from arq.jobs import Job,JobStatus,ResultNotFound,JobResult,JobDef
from dataclasses import asdict
from app.definition._error import BaseError
from app.definition._service import BaseService, Service
from app.services.config_service import ConfigService, UvicornWorkerService
from app.services.file.file_service import FileService
from app.utils.constant import RedisConstant
from app.services.database.redis_service import RedisService


QUEUE_NAME = 'arq:data_loader_task'

class DataTaskNotFoundError(BaseError):
    def __init__(self, job_id:str,reason:str):
        super().__init__(job_id,reason)
        self.job_id = job_id
        self.reason = reason

class JobDoesNotExistsError(BaseError):
    def __init__(self, job_id:str,reason:str,raise_on_exists):
        super().__init__()
        self.job_id = job_id
        self.reason = reason

@Service()
class ArqService(BaseService):

    @staticmethod
    def create_arq_url(user,password)->str:
        return f"redis://{user}:{password}@redis:6379/{RedisConstant.EVENT_DB}"

    def build(self, build_state = ...):
        self.arq_url = ArqService.create_arq_url(self.redisService.db_user,self.redisService.db_password)
        self.queue = QUEUE_NAME

    def __init__(self,fileService:FileService,redisService:RedisService,configService:ConfigService,UvicornWorkerService:UvicornWorkerService):
        self.fileService = fileService
        self.redisService = redisService
        self.configService = configService
        self.uvicornWorkerService = UvicornWorkerService      
        super().__init__()  
        
    def register_task(self,tasks:list[Callable]):
        self.task_registry = [t.__name__ for t in tasks]

    async def initialize(self):
        redisSettings = RedisSettings.from_dsn(self.arq_url)
        self._worker = await create_pool(redisSettings)

    async def close(self):
        await self._worker.close()

    async def enqueue_task(self,task_name:str,_job_id:str=None,kwargs:dict={}):
        if task_name not in self.task_registry:
            raise DataTaskNotFoundError(task_name)
        await self._worker.enqueue_job(task_name,job_id=_job_id,_queue_name=self.queue,**kwargs)
    
    async def get_queued_jobs(self,):
        jobs = await self._worker.queued_jobs(queue_name=self.queue)
        return [asdict(j) for j in jobs]
        
    async def get_jobs_results(self):
        jobs = await self._worker.all_job_results()
        return [asdict(j) for j in jobs]

    async def fetch_job(self,job_id:str):
        return Job(job_id,self,self.queue)
    
    async def job_info(self,job_id:str|Job):
        if isinstance(job_id,str):
            job_id = await self.fetch_job(job_id)
        
        return await job_id.info()
    
    async def abort_job(self,job_id:str|Job)->bool:
        if isinstance(job_id,str):
            job_id = await self.fetch_job(job_id)
        return await job_id.abort()

    async def state_after_abort(job:Job)->Literal['deleted','cancelled']:
        status = await job.status()
        if status == JobStatus.not_found:
            return "deleted"

        info = await job.result_info()
        if info and info.success is False:
            return "cancelled"

        return "deleted"
    
    async def job_results(self,job_id:str|Job):
        if isinstance(job_id,str):
            job_id = await self.fetch_job(job_id)
        
        info = await job_id.result_info()
        if info == None:
            raise ResultNotFound
        return info
        
    async def job_exists(self,job_id:str,raise_on_exist=False):
        job = await self.fetch_job(job_id)
        status:JobStatus = await  job.status()
        if status == JobStatus.not_found and not raise_on_exist:
            raise JobDoesNotExistsError(job_id,'does not exists',raise_on_exist)
        if status == JobStatus.complete and not raise_on_exist:
            raise JobDoesNotExistsError(job_id,'job as been completed',raise_on_exist)
        if raise_on_exist:
            raise JobDoesNotExistsError(job_id,'job already exists',raise_on_exist)

        return job
    
            