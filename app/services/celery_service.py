import asyncio
from typing import Any, Callable, ParamSpec
import typing
from app.classes.celery import CelerySchedulerOptionError, CeleryTaskNotFoundError,SCHEDULER_RULES
from app.classes.celery import  CeleryTask, SchedulerModel
from app.definition._service import Service, ServiceClass, ServiceStatus
from app.interface.timers import IntervalInterface
from app.utils.constant import HTTPHeaderConstant
from .config_service import ConfigService
from app.utils.helper import generateId
from app.task import TASK_REGISTRY,celery_app,AsyncResult,task_name
from redbeat  import RedBeatSchedulerEntry
from app.utils.helper import generateId
import datetime as dt
from fastapi import BackgroundTasks, Request, Response
from starlette.background import BackgroundTask
from redis import Redis

P = ParamSpec("P")

@ServiceClass
class BackgroundTaskService(BackgroundTasks,Service):
    def __init__(self,configService:ConfigService):
        self.configService = configService
        self.running_tasks_count = 0
        self.sharing_task: dict[str,list[Callable]] = {}
        self.task_lock = asyncio.Lock()
        super().__init__(None)
        Service.__init__(self)
         
    def _register_tasks(self,request_id:str):
        self.sharing_task[request_id] = []
    
    def _delete_tasks(self, request_id:str):
        try:
            del self.sharing_task[request_id]
        except:
            ...

    def add_task(self,request_id:str,func: typing.Callable[P, typing.Any], *args: P.args, **kwargs: P.kwargs) -> None:
        task = BackgroundTask(func, *args, **kwargs)
        self.sharing_task[request_id].append(task)
        
    def build(self):
        ...

    @property
    async def global_task_count(self):
        async with self.task_lock:
            return self.running_tasks_count
    
    async def __call__(self,request_id:str) -> None:
        
        async with self.task_lock:
            self.running_tasks_count += len(self.sharing_task[request_id])  # Increase count based on new tasks

        for task in self.sharing_task[request_id]:
            await task()

        async with self.task_lock:
            self.running_tasks_count -= len(self.sharing_task[request_id])  # Decrease count after tasks complete
            self._delete_tasks(request_id)

    @staticmethod
    def populate_response_with_request_id(request:Request, response: Response):
        response.headers[HTTPHeaderConstant.REQUEST_ID] = request.state.request_id

@ServiceClass
class CeleryService(Service, IntervalInterface):
    _celery_app = celery_app
    _task_registry = TASK_REGISTRY

    def __init__(self,configService:ConfigService,bTaskService:BackgroundTaskService):
        Service.__init__(self)
        IntervalInterface.__init__(self)
        self.configService = configService
        self.bTaskService = bTaskService
        self.available_workers_count = -1
        self.worker_not_available_count = 0

        self.timeout_count = 0
        self.task_lock = asyncio.Lock()
    
        #self.redis_client = Redis(host='localhost', port=6379, db=0)# set from config
        
    def trigger_task_from_scheduler(self,scheduler:SchedulerModel,*args,**kwargs):
        celery_task = scheduler.model_dump(mode='python',exclude={'content'})
        celery_task: CeleryTask = CeleryTask(args=args,kwargs=kwargs,**celery_task)
        return self._trigger_task(celery_task,scheduler.schedule_name)

    def trigger_task_from_task(self,celery_task:CeleryTask,schedule_name:str= None):
        return self._trigger_task(celery_task,schedule_name)

    def _trigger_task(self,celery_task:CeleryTask,schedule_name:str=None):
        schedule_id = schedule_name if schedule_name is not None else generateId(25)
        c_type = celery_task['task_type']
        t_name = celery_task['task_name']
        now = dt.datetime.now()
        result = {'message': f'[{now}] - Task [{t_name}] received successfully'}
        
        if c_type == 'now':
            task_result = self._task_registry[t_name]['task'].delay(*celery_task['args'],**celery_task['kwargs'])
            result.update({'task_id':task_result.id,'type':'task'})
            return result

        options = celery_task['task_option']
        if c_type == 'once':
            task_result = self._task_registry[t_name]['task'].apply_async(**options,args=celery_task['args'],kwargs=celery_task['kwargs'])
            result.update({'task_id':task_result.id,'type':'task'})
            return task_result.id

        schedule = SCHEDULER_RULES[c_type]
        try:
            schedule = schedule(**options) # ERROR
        except ValueError:
            raise CelerySchedulerOptionError
        
        entry = RedBeatSchedulerEntry(schedule_id,t_name,schedule,args=celery_task['args'],kwargs=celery_task['kwargs'],app=self._celery_app)
        entry.save()
        result.update({'task_id':schedule_id,'type':'schedule'})
        return result

    def cancel_task(self,task_id,force=False):
        result = AsyncResult(task_id, app=self._celery_app)

        if result.state in ["PENDING", "RECEIVED"]:
            result.revoke(terminate=False)

        elif result.state in ["STARTED"]:
            if force:
                result.revoke(terminate=True, signal="SIGTERM")

    def delete_schedule(self,schedule_id:str):
        try:
            schedule_id = f'redbeat:{schedule_id}'
            entry = RedBeatSchedulerEntry.from_key(schedule_id,app=self._celery_app)
            entry.delete()
        except KeyError:
            raise CeleryTaskNotFoundError

    def seek_schedule(self,schedule_id:str):
        try:
            schedule_id = f'redbeat:{schedule_id}'
            entry = RedBeatSchedulerEntry.from_key(schedule_id,app=self._celery_app)
            return {
                'total_run_count':entry.total_run_count,
                'due_at':entry.due_at,
                'schedule':entry.schedule,
                'last_run_at':entry.last_run_at
            }
        except KeyError:
            raise CeleryTaskNotFoundError

    def seek_result(self, task_id: str):
        try:
            result = AsyncResult(task_id, app=self._celery_app)
            response = {
                'task_id': result.id,
                'status': result.status,
                'result': result.result,
                'traceback': result.traceback,
                'date_done': result.date_done,
                'successful': result.successful()
            }
            return response
        except KeyError:
            raise CeleryTaskNotFoundError
    
    def manually_set_task_expires_result(self,expires:int,scheduler:SchedulerModel):
        raise NotImplementedError
        if scheduler.task_type == 'now':
            self.redis_client.expire(f'celery-task-meta-{scheduler.task_name}', 3600)  # Expire in 1 hour
        
    def build(self):
        ...

    @property
    def set_next_timeout(self):
        if self.timeout_count >= 30:
            return 60
        return 1 *(1.1 ** self.timeout_count)

    async def _check_workers_status(self):
        try:
            response = celery_app.control.ping(timeout=self.set_next_timeout)
            available_workers_count = len(response)
            if  available_workers_count == 0:
                self.service_status = ServiceStatus.TEMPORARY_NOT_AVAILABLE
                async with self.task_lock:
                    self.available_workers_count = 0
            
            async with self.task_lock:
                self.available_workers_count = available_workers_count 
            self.worker_not_available = self.configService.CELERY_WORKERS_COUNT - available_workers_count       
            self.timeout_count=0             
        except Exception as e:
            self.timeout_count +=1
            async with self.task_lock:
                    self.available_workers_count = 0
    
    @property
    async def get_available_workers_count(self)->float:
        async with self.task_lock:
            return self.available_workers_count

    async def pingService(self,ratio:float=None,count:int=None):
        response_count = await self.get_available_workers_count
        if ratio:
            # TODO check in which interval the ratio is in
            return super().pingService()
        if count:
            # TODO check in which interval the ratio is in
            return super().pingService()
        return response_count, response_count/self.configService.CELERY_WORKERS_COUNT

    def callback(self):
        asyncio.create_task(self._check_workers_status())
