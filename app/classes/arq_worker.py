from arq.connections import RedisSettings,create_pool,ArqRedis
from arq.jobs import Job,JobStatus
from dataclasses import asdict
from app.definition._error import BaseError
from app.utils.constant import RedisConstant


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

class ArqWorker:

    @staticmethod
    def create_arq_url(user,password)->str:
        return f"redis://{user}:{password}@redis:6379/{RedisConstant.EVENT_DB}"

    def __init__(self,user,password,task_registry,queue:str):
        self.arq_url = ArqWorker.create_arq_url(user,password)
        self.task_registry = task_registry
        self.queue = queue

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
        
    async def job_exists(self,job_id:str,raise_on_exist=False):
        job = await self.fetch_job(job_id)
        status:JobStatus = await  job.status()
        if status == JobStatus.not_found and not raise_on_exist:
            raise JobDoesNotExistsError(job_id,'does not exists',raise_on_exist)
        if status == JobStatus.complete and not raise_on_exist:
            raise JobDoesNotExistsError(job_id,'job as been completed',raise_on_exist)
        if raise_on_exist:
            raise JobDoesNotExistsError(job_id,'job already exists',raise_on_exist)

        return True
    
            