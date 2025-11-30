from fastapi import Response
from kombu import Queue
from typing import Any, Callable, Literal, Self
from aiorwlock import RWLock
from celery.result import AsyncResult
from redbeat import RedBeatSchedulerEntry
from app.classes.celery import CeleryNotAvailableError, CeleryTask, CeleryTaskNotFoundError, InspectMode, SchedulerModel, TaskExecutionResult, TaskType, add_warning_messages, due_entry_timedelta
from app.definition._service import BaseMiniService, BaseMiniServiceManager, BaseService, LinkDep, MiniService, MiniServiceStore, Service, ServiceStatus
from app.interface.timers import IntervalInterface
from app.models.communication_model import BaseProfileModel
from app.services.config_service import ConfigService
from app.services.database_service import RabbitMQService, RedisService
from app.tasks import TASK_REGISTRY, celery_app, task_name
from app.services.profile_service import ProfileMiniService, ProfileService
from app.errors.service_error import BuildError, BuildFailureError, BuildOkError, ServiceNotAvailableError
from app.utils.constant import CeleryConstant, RedisConstant, SpecialKeyParameterConstant
import datetime as dt
from humanize import naturaldelta,naturaltime
from uuid import uuid4
from app.utils.tools import RunInThreadPool
from app.classes.scheduler import schedule

CHANNEL_BUILD_STATE=0

@Service(
    links=[LinkDep(ProfileService,to_build=True,build_state=CHANNEL_BUILD_STATE)]
)
class CeleryService(BaseMiniServiceManager, IntervalInterface):
    _non_redbeat_task_type = {TaskType.NOW,TaskType.DATETIME,TaskType.TIMEDELTA}

    def __init__(self, configService: ConfigService,redisService:RedisService,profileService:ProfileService,rabbitmqService:RabbitMQService):
        BaseService.__init__(self)
        IntervalInterface.__init__(self,False)

        self.configService = configService
        self.profileService = profileService
        self.redisService = redisService
        self.rabbitmqService = rabbitmqService
        self._workers = {}

        self.timeout_count = 0
        self.task_lock = RWLock()
        self.MiniServiceStore = MiniServiceStore[ChannelMiniService](self.__class__.__name__)
    
    def trigger_task_from_scheduler(self, scheduler: SchedulerModel,index:int|None,weight:float=-1.0, *args, **kwargs):
        schedule_id = str(uuid4())
        t_name = scheduler.task_name
        result = TaskExecutionResult(expected_tbd=None,date= str(dt.datetime.now()),offloaded=True,handler='Celery',index=index,result=None,message=f'Task [{t_name}] received successfully',heaviness=str(scheduler._heaviness))
        option = scheduler.task_option.model_dump()
        
        if scheduler.task_type in self._non_redbeat_task_type:
            
            if scheduler.task_type != TaskType.NOW:
                option['eta'] = scheduler._schedule._beat_object
                expected_tbd = naturaldelta(option['eta'])
            else:
                expected_tbd = naturaldelta(option.get('countdown', None))
            
            task_result = TASK_REGISTRY[t_name]['task'].apply_async(**option, args=args, kwargs=kwargs)
            result.update(task_result.id,'task',expected_tbd)
        else:
            entry = RedBeatSchedulerEntry(schedule_id, t_name, scheduler._schedule._beat_object, args=args, kwargs=kwargs, app=celery_app,options=option).save()
            time = due_entry_timedelta(entry)
            result.update(schedule_id,'schedule',None if time == None else naturaldelta(time))

        return result

    def cancel_task(self, task_id, force=False):
        result = AsyncResult(task_id, app=celery_app)

        if result.state in ["PENDING", "RECEIVED"]:
            result.revoke(terminate=False)

        elif result.state in ["STARTED"]:
            if force:
                result.revoke(terminate=True, signal="SIGTERM")

    def delete_schedule(self, schedule_id: str):
        try:
            schedule_id = f'redbeat:{schedule_id}'
            entry = RedBeatSchedulerEntry.from_key(schedule_id, app=celery_app)
            entry.delete()
        except KeyError:
            raise CeleryTaskNotFoundError

    def seek_schedule(self, schedule_id: str):
        try:
            schedule_id = f'redbeat:{schedule_id}'
            entry = RedBeatSchedulerEntry.from_key(
                schedule_id, app=celery_app)
            return {
                'total_run_count': entry.total_run_count,
                'due_at': entry.due_at,
                'schedule': entry.schedule,
                'last_run_at': entry.last_run_at
            }
        except KeyError:
            raise CeleryTaskNotFoundError

    def seek_result(self, task_id: str):
        try:
            result = AsyncResult(task_id, app=celery_app)
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
    
    def verify_dependency(self):
        if self.configService.CELERY_WORKERS_EXPECTED < 1:
            raise BuildOkError('No workers expected')
        
        if self.configService.CELERY_BROKER not in ['rabbitmq','redis']:
            raise BuildOkError('')
        
        if self.configService.CELERY_BROKER == 'redis' and self.redisService.service_status == ServiceStatus.NOT_AVAILABLE:
            raise BuildOkError('')

        if self.configService.CELERY_BROKER == 'rabbitmq' and self.rabbitmqService.service_status == ServiceStatus.NOT_AVAILABLE:
            raise BuildOkError('')
         
    def build(self,build_state=-1):
        
        self.state_counter = self.StatusCounter(len(self.profileService.MiniServiceStore))
        self.MiniServiceStore.clear()
        
        for id,p in self.profileService.MiniServiceStore:

            miniService = ChannelMiniService(p,self.configService,self.rabbitmqService,self.redisService,self)
            miniService._builder(BaseMiniService.QUIET_MINI_SERVICE, build_state, self.CONTAINER_LIFECYCLE_SCOPE)

            self.state_counter.count(miniService)
            self.MiniServiceStore.add(miniService)

        self._builded = True
        self._destroyed = False
        try:
            BaseMiniServiceManager.build(self,self.state_counter,build_state)
        except BuildError:
            raise BuildOkError
    
    @property
    def set_next_timeout(self):
        if self.timeout_count >= 30:
            return 60
        return 1 * (1.1 ** self.timeout_count)

    async def _check_workers_status(self):
        response = await self.ping(timeout=2)
        async with self.statusLock.writer:
            self._workers = response.copy()

    @property
    async def workers(self):
        async with self.task_lock.reader:
            return self._workers

    async def pingService(self,infinite_wait:bool,data:dict,profile:str=None,as_manager:bool=False,**kwargs):
        if kwargs.get('__celery_availability__',False) and self.service_status != ServiceStatus.AVAILABLE:
            raise ServiceNotAvailableError('Absolutely need celery to be available')

        _scheduler:SchedulerModel = data.get('scheduler',None)
        if _scheduler:
            if _scheduler.task_type == TaskType.SOLAR and self.configService.CELERY_WORKERS_EXPECTED < 1:
                raise CeleryNotAvailableError('task_type SOLAR is not possible to parse in other scheduler since no workers are available')

            if _scheduler.task_type == TaskType.RRULE and self.configService.CELERY_WORKERS_EXPECTED < 1:
                raise CeleryNotAvailableError('Use task_type INTERVAL to achieve a similar process since it is not possible to parse this type to other scheduler services')

            if self.configService.CELERY_WORKERS_EXPECTED >= 1:
                await super().pingService(infinite_wait,data,profile,as_manager,**kwargs)


    async def callback(self):
        if self.configService.CELERY_WORKERS_EXPECTED >= 1:
            await self._check_workers_status()

    @RunInThreadPool
    def revoke(self,tasks:list[str],timeout=5):
        return celery_app.control.revoke(tasks)

    @RunInThreadPool
    def inspect(self,mode:InspectMode,destination:list[str]=None,timeout=None):
        inspect = celery_app.control.inspect(destination)
        match mode:
            case 'active':
                return inspect.active()
            case 'active_queue':
                return inspect.active_queues()
            case 'registered':
                return inspect.registered()
            case 'scheduled':
                return inspect.scheduled()
            case 'stats':
                return inspect.stats()
            case 'reserved':
                return inspect.reserved()

            case _:
                raise 

    @RunInThreadPool
    def ping(self,destination:list[str]=None,timeout=2):
        if timeout == None:
            timeout = self.set_next_timeout
        return celery_app.control.ping(timeout=timeout,destination=destination)

    @RunInThreadPool
    def shutdown(self,destination:list[str]=None,timeout=None):
        return self._broadcast('shutdown',destination=destination,reply=True)
    
    @RunInThreadPool
    def _broadcast(self,command:str,destination:list[str]=None,reply=True,timeout=None):
        return celery_app.control.broadcast(command,destination=destination,reply=reply,timeout=timeout)
    

@MiniService()
class ChannelMiniService(BaseMiniService):

    def __init__(self, depService:ProfileMiniService[BaseProfileModel],configService:ConfigService,rabbitmqService:RabbitMQService,redisService:RedisService,celeryService:CeleryService):
        self.depService = depService
        super().__init__(depService,None)
        self.redisService = redisService
        self.celeryService = celeryService
        self.configService = configService
        self.rabbitmqService = rabbitmqService
    
    async def pingService(self,infinite_wait:bool,data:dict,profile:str=None,as_manager:bool=False,**kwargs):
        """
        the worker can take care of the request
        """

        if kwargs.get('__channel_availability__',False) and self.service_status != ServiceStatus.AVAILABLE:
            raise ServiceNotAvailableError()
        
        scheduler:SchedulerModel = data.get('scheduler',None)
        taskManager = data.get('taskManager',None)
        # add warning if queue is <<congestionné>> and later change algorithm
        #add_warning_messages(None,scheduler,None)
        # TODO if the celery queue is not available only let scheduler with now to pass, but retry is not available
        ...

    def build(self, build_state = ...):
        if self.celeryService.service_status != ServiceStatus.AVAILABLE:
            raise BuildOkError
        
    @staticmethod
    def celery_guard(func:Callable):     

        async def wrapper(self:Self,*args,response:Response=None,**kwargs):
            if self.celeryService.service_status != ServiceStatus.AVAILABLE:
                if response != None:
                    ...
                return
            return await func(self,*args,**kwargs)
        
        return wrapper

    @celery_guard
    @RunInThreadPool
    async def refresh_worker_state(self):
        await self.pause_worker()
        reply = celery_app.control.broadcast(CeleryConstant.REFRESH_PROFILE_WORKER_STATE_COMMAND,arguments={'p':self.queue},reply=True)
        return reply

    @celery_guard
    @RunInThreadPool
    async def purge_queue(self):
        """
        Purge the Celery queue.
        If queue_name is provided, it will purge that specific queue.
        If not, it will purge all queues.
        """
        await self.pause_worker()
        with celery_app.connection_or_acquire() as conn:
            queue = Queue(self.queue, exchange=None, routing_key=self.queue)
            val = queue(conn).purge()
            print(val)
            return val

    @celery_guard
    @RunInThreadPool
    def pause_worker(self,destination:list[str]=None,timeout=1.5):
        return celery_app.control.cancel_consumer(self.queue, reply=True,destination=destination,timeout=timeout)

    @celery_guard
    @RunInThreadPool
    def resume_worker(self,destination:list[str]=None,timeout=1.5):
        return celery_app.control.add_consumer(self.queue, reply=True,timeout=timeout,destination=destination)

    @celery_guard
    @RunInThreadPool
    async def delete_queue(self):
        await self.pause_worker()
        if self.configService.CELERY_BROKER == 'redis':
            return await self.redisService.delete_all(RedisConstant.CELERY_DB,self.queue)
        else:
            with celery_app.connection_or_acquire() as conn:
                queue = Queue(self.queue, exchange=None, routing_key=self.queue)
                queue(conn).delete()

    @celery_guard
    @RunInThreadPool
    def create_queue(self):
        return celery_app.control.add_consumer(self.queue, reply=True)

    @property
    def queue(self):
        return self.depService.queue_name
