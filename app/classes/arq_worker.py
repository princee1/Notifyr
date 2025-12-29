from arq.connections import RedisSettings,create_pool,ArqRedis
from arq.jobs import Job
from dataclasses import asdict

from fastapi import HTTPException
from app.utils.constant import RedisConstant

class ArqWorker:


    def __init__(self,arq_url,task_registry,queue:str):
        self.arq_url = arq_url
        self.task_registry = task_registry
        self.queue = queue

    async def initialize(self):
        redisSettings = RedisSettings.from_dsn(self.arq_url)
        self._worker = await create_pool(redisSettings)

    async def close(self):
        await self._worker.close()

    async def enqueue_task(self,task_name:str,_job_id:str=None,kwargs:dict={}):
        if task_name not in self.task_registry:
            raise HTTPException(status_code=400, detail=f"Task {task_name} is not registered.")
        await self._worker.enqueue_job(task_name,job_id=_job_id,_queue_name=self.queue,**kwargs)
    
    async def get_queued_jobs(self,):
        jobs = await self._worker.queued_jobs(queue_name=self.queue)
        return [asdict(j) for j in jobs]
        
    async def get_jobs_results(self):
        jobs = await self._worker.all_job_results()
        return [asdict(j) for j in jobs]

    async def fetch_job(self,job_id):
        return Job(job_id,self,self.queue)
        
    async def job_exists(self,):
        ...

    async def job_result_exists(self):
        ...