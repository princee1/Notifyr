from typing import Any
from aiorwlock import RWLock
from celery.result import AsyncResult
from redbeat import RedBeatSchedulerEntry
from app.classes.celery import CeleryTask, CeleryTaskNotFoundError, SchedulerModel, TaskExecutionResult, TaskType
from app.definition._service import BaseMiniService, BaseMiniServiceManager, BaseService, LinkDep, MiniService, MiniServiceStore, Service, ServiceStatus
from app.interface.timers import IntervalInterface
from app.models.communication_model import BaseProfileModel
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.task import TASK_REGISTRY, celery_app, task_name
from app.services.profile_service import ProfileMiniService, ProfileService
from app.errors.service_error import BuildError, BuildFailureError, BuildOkError, BuildSkipError
from app.utils.constant import SpecialKeyParameterConstant
from app.utils.helper import generateId
import datetime as dt
from humanize import naturaldelta





CHANNEL_BUILD_STATE=0

@MiniService()
class QueueMiniService(BaseMiniService):

    def __init__(self, depService:ProfileMiniService[BaseProfileModel]):
        self.depService = depService
        super().__init__(depService,None)
    
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

    def purge(self):
        """
        Purge the Celery queue.
        If queue_name is provided, it will purge that specific queue.
        If not, it will purge all queues.
        """
        count = self.celeryService.celery_app.control.purge(queue=self.miniService_id)
        return {'message': 'Celery queue purged successfully.', 'count': count}
        
    def pause(self):
        ...

    def resume(self):
        ...

    def delete(self):
        ...
    
    def create(self):
        ...


@Service(
    links=[LinkDep(ProfileService,to_build=True,build_state=CHANNEL_BUILD_STATE)]
)
class CeleryService(BaseMiniServiceManager, IntervalInterface):
    _celery_app = celery_app
    _task_registry = TASK_REGISTRY

    def __init__(self, configService: ConfigService,redisService:RedisService,profileService:ProfileService):
        BaseService.__init__(self)
        IntervalInterface.__init__(self,False)
        self.configService = configService

        self.redisService = redisService
        self.available_workers_count = -1
        self.worker_not_available_count = 0

        self.timeout_count = 0
        self.task_lock = RWLock()
        self.MiniServiceStore = MiniServiceStore[QueueMiniService](self.__class__.__name__)


    def trigger_task_from_scheduler(self, scheduler: SchedulerModel,index:int|None, *args, **kwargs):
        params = self.scheduler_to_celery_task(scheduler,index,*args,**kwargs)
        return self._trigger_task(**params)

    def trigger_task_from_task(self, celery_task: CeleryTask,index:int|None, schedule_name: str = None):
        return self._trigger_task(celery_task, schedule_name,index)

    def scheduler_to_celery_task(self,scheduler: SchedulerModel,index:int|None, *args, **kwargs):
        celery_task = scheduler.model_dump(mode='python', exclude={'content','sender_type','filter_error','scheduler_option'})
        celery_task: CeleryTask = CeleryTask(args=args, kwargs=kwargs,schedule=scheduler._scheduler, **celery_task)
        return {
            'celery_task':celery_task,
            'index':index,
            'schedule_name':scheduler.schedule_name
        }

    def _trigger_task(self, celery_task: CeleryTask, schedule_name: str = None,index:int|None=None):
        schedule_id = schedule_name if schedule_name is not None else generateId(25)
        c_type = celery_task['task_type']
        t_name = celery_task['task_name']
        result = TaskExecutionResult(date= str(dt.datetime.now()),offloaded=True,handler='Celery',index=index,result=None,message=f'Task [{t_name}] received successfully',heaviness=str(celery_task['heaviness']))

        option = celery_task.get('task_option',{})
        if c_type == 'now':
            task_result = self._task_registry[t_name]['task'].apply_async(**option, args=celery_task['args'], kwargs=celery_task['kwargs'])
            eta = (dt.datetime.now() + dt.timedelta(seconds=option.get('countdown', 0)))
            time_until_first_run = (eta - dt.datetime.now()).total_seconds() if eta else None
            result.update(task_result.id,'task',naturaldelta(time_until_first_run) if time_until_first_run else None)
            return result

        schedule = celery_task['schedule']
        entry = RedBeatSchedulerEntry(schedule_id, t_name, schedule, args=celery_task['args'], kwargs=celery_task['kwargs'], app=self._celery_app)
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
        result = AsyncResult(task_id, app=self._celery_app)

        if result.state in ["PENDING", "RECEIVED"]:
            result.revoke(terminate=False)

        elif result.state in ["STARTED"]:
            if force:
                result.revoke(terminate=True, signal="SIGTERM")

    def delete_schedule(self, schedule_id: str):
        try:
            schedule_id = f'redbeat:{schedule_id}'
            entry = RedBeatSchedulerEntry.from_key(schedule_id, app=self._celery_app)
            entry.delete()
        except KeyError:
            raise CeleryTaskNotFoundError

    def seek_schedule(self, schedule_id: str):
        try:
            schedule_id = f'redbeat:{schedule_id}'
            entry = RedBeatSchedulerEntry.from_key(
                schedule_id, app=self._celery_app)
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
    
    def verify_dependency(self):
        if self.redisService.service_status == ServiceStatus.NOT_AVAILABLE:
            raise BuildFailureError

    def build(self,build_state=-1):
        
        self.state_counter = self.StatusCounter(len(self.profileService.MiniServiceStore))
        self.MiniServiceStore.clear()
        
        for id,p in self.profileService.MiniServiceStore:

            miniService = QueueMiniService(p,self.celeryService)
            miniService._builder(BaseMiniService.QUIET_MINI_SERVICE, build_state, self.CONTAINER_LIFECYCLE_SCOPE)

            self.state_counter.count(miniService)
            self.MiniServiceStore.add(miniService)
               
        try:
            self._builded = True
            self._destroyed = False
            BaseMiniServiceManager.build(self,self.state_counter)
        except BuildError:
            raise BuildSkipError
        
    @property
    def set_next_timeout(self):
        if self.timeout_count >= 30:
            return 60
        return 1 * (1.1 ** self.timeout_count)

    async def _check_workers_status(self):
        try:
            response = celery_app.control.ping(timeout=self.set_next_timeout)
            available_workers_count = len(response)
            if available_workers_count == 0:
                self.service_status = ServiceStatus.PARTIALLY_AVAILABLE
                async with self.task_lock.writer:
                    self.available_workers_count = 0

            async with self.task_lock.reader:
                self.available_workers_count = available_workers_count
            self.worker_not_available_count = self.configService.CELERY_WORKERS_COUNT - \
                available_workers_count
            self.timeout_count = 0
        except Exception as e:
            self.timeout_count += 1
            async with self.task_lock.writer:
                self.available_workers_count = 0

    @property
    async def get_available_workers_count(self) -> int:
        async with self.task_lock.reader:
            return self.available_workers_count

    async def async_pingService(self,infinite_wait:bool, **kwargs):
        ...

    async def callback(self):
        await self._check_workers_status()

    def shutdown(self):
        ...
    
    def broadcast(self):
        ...

    def stats(self):
        ...