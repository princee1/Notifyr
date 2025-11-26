from kombu import Queue
from typing import Any, Literal
from aiorwlock import RWLock
from celery.result import AsyncResult
from redbeat import RedBeatSchedulerEntry
from app.classes.celery import CeleryTask, CeleryTaskNotFoundError, InspectMode, SchedulerModel, TaskExecutionResult, TaskType
from app.definition._service import BaseMiniService, BaseMiniServiceManager, BaseService, LinkDep, MiniService, MiniServiceStore, Service, ServiceStatus
from app.interface.timers import IntervalInterface
from app.models.communication_model import BaseProfileModel
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.tasks import TASK_REGISTRY, celery_app, task_name
from app.services.profile_service import ProfileMiniService, ProfileService
from app.errors.service_error import BuildError, BuildFailureError, BuildOkError, BuildSkipError
from app.utils.constant import CeleryConstant, RedisConstant, SpecialKeyParameterConstant
from app.utils.helper import generateId
import datetime as dt
from humanize import naturaldelta
from uuid import uuid4

from app.utils.tools import RunInThreadPool


CHANNEL_BUILD_STATE=0


@MiniService()
class ChannelMiniService(BaseMiniService):

    def __init__(self, depService:ProfileMiniService[BaseProfileModel],redisService:RedisService):
        self.depService = depService
        super().__init__(depService,None)
        self.redisService = redisService
    
    async def async_pingService(self,infinite_wait:bool, **kwargs):
        route_params:dict[str,Any] = kwargs.get(SpecialKeyParameterConstant.ROUTE_PARAMS_KWARGS_PARAMETER,{})
        scheduler:SchedulerModel = route_params.get('scheduler',None)
        if not scheduler:
            return
        if scheduler.task_type == TaskType.NOW:
            return
        
        # TODO if the celery queue is not available only let scheduler with now to pass, but retry is not available
        ...

    def build(self, build_state = ...):
        raise BuildOkError

    @RunInThreadPool
    async def refresh_worker_state(self):
        await self.pause_worker()
        reply = celery_app.control.broadcast(CeleryConstant.REFRESH_PROFILE_WORKER_STATE_COMMAND,arguments={'p':self.queue},reply=True)
        return reply

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
    
    @RunInThreadPool
    def pause_worker(self,destination:list[str]=None,timeout=1.5):
        return celery_app.control.cancel_consumer(self.queue, reply=True,destination=destination,timeout=timeout)

    @RunInThreadPool
    def resume_worker(self,destination:list[str]=None,timeout=1.5):
        return celery_app.control.add_consumer(self.queue, reply=True,timeout=timeout,destination=destination)

    @RunInThreadPool
    async def delete_queue(self):
        await self.pause_worker()
        return await self.redisService.delete_all(RedisConstant.CELERY_DB,self.queue)

    @RunInThreadPool
    def create_queue(self):
        return celery_app.control.add_consumer(self.queue, reply=True)

    @property
    def queue(self):
        return self.depService.queue_name

@Service(
    links=[LinkDep(ProfileService,to_build=True,build_state=CHANNEL_BUILD_STATE)]
)
class CeleryService(BaseMiniServiceManager, IntervalInterface):

    def __init__(self, configService: ConfigService,redisService:RedisService,profileService:ProfileService):
        BaseService.__init__(self)
        IntervalInterface.__init__(self,False)

        self.configService = configService
        self.profileService = profileService
        self.redisService = redisService
    
        self.timeout_count = 0
        self.task_lock = RWLock()
        self.MiniServiceStore = MiniServiceStore[ChannelMiniService](self.__class__.__name__)

    def trigger_task_from_scheduler(self, scheduler: SchedulerModel,index:int|None,weight:float=-1.0, *args, **kwargs):
        celery_task = scheduler.model_dump(mode='python', exclude={'content','sender_type','filter_error','scheduler_option'})
        celery_task: CeleryTask = CeleryTask(args=args, kwargs=kwargs,schedule=scheduler._scheduler, **celery_task)
        schedule_id = scheduler.schedule_name if scheduler.schedule_name is not None else str(uuid4())
        c_type = celery_task['task_type']
        t_name = celery_task['task_name']
        result = TaskExecutionResult(date= str(dt.datetime.now()),offloaded=True,handler='Celery',index=index,result=None,message=f'Task [{t_name}] received successfully',heaviness=str(celery_task['heaviness']))

        option = celery_task.get('task_option',{})
        if c_type == 'now':
            task_result = TASK_REGISTRY[t_name]['task'].apply_async(**option, args=celery_task['args'], kwargs=celery_task['kwargs'])
            eta = (dt.datetime.now() + dt.timedelta(seconds=option.get('countdown', 0)))
            time_until_first_run = (eta - dt.datetime.now()).total_seconds() if eta else None
            result.update(task_result.id,'task',naturaldelta(time_until_first_run) if time_until_first_run else None)
            return result

        schedule = celery_task['schedule']
        entry = RedBeatSchedulerEntry(schedule_id, t_name, schedule, args=celery_task['args'], kwargs=celery_task['kwargs'], app=celery_app)
        entry.save()
        if isinstance(entry.due_at,dt.datetime):
            time =entry.due_at.utcoffset().seconds
        elif isinstance(entry.due_at,(float,int)):
            time = entry.due_at
        else:
            time = None
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
        if self.redisService.service_status == ServiceStatus.NOT_AVAILABLE:
            raise BuildFailureError

    def build(self,build_state=-1):
        
        self.state_counter = self.StatusCounter(len(self.profileService.MiniServiceStore))
        self.MiniServiceStore.clear()
        
        for id,p in self.profileService.MiniServiceStore:

            miniService = ChannelMiniService(p,self.redisService)
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

    async def async_pingService(self,infinite_wait:bool, **kwargs):
        ...

    async def callback(self):
        await self._check_workers_status()

    def rate_limit(self,task_name:str,rate_limit,destination:list[str]=None):
        return celery_app.control.rate_limit(task_name, rate_limit,
           destination=destination,reply=True,timeout=5)

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
    
    async def delete_queue_type(self,):
        ...