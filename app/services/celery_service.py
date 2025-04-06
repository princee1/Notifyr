import asyncio
from sched import scheduler
from typing import Any, Callable, Coroutine, Literal, ParamSpec, TypedDict
import typing
from app.classes.celery import CelerySchedulerOptionError, CeleryTaskNotFoundError, SCHEDULER_RULES, TaskHeaviness, TaskType
from app.classes.celery import CeleryTask, SchedulerModel
from app.definition._service import Service, ServiceClass, ServiceStatus,BuildWarningError
from app.interface.timers import IntervalInterface, SchedulerInterface
from app.services.database_service import RedisService
from app.utils.constant import HTTPHeaderConstant
from .config_service import ConfigService
from app.utils.helper import generateId
from app.task import TASK_REGISTRY, celery_app, AsyncResult, task_name
from redbeat import RedBeatSchedulerEntry
from app.utils.helper import generateId
import datetime as dt
from fastapi import BackgroundTasks, Request, Response
from starlette.background import BackgroundTask
from redis import Redis
from humanize import naturaltime, naturaldelta
from prometheus_client import Counter,Histogram,Gauge

P = ParamSpec("P")
RunType = Literal['parallel','concurrent']

class TaskConfig(TypedDict):
    task: BackgroundTask | Coroutine
    heaviness: TaskHeaviness
    save_result: bool
    ttl: int
    ttd: float
    running_type:Literal['parallel','concurrent'] = 'concurrent'

class Task(TypedDict):
    meta:dict
    taskConfig:list[TaskConfig]

@ServiceClass
class TaskService(BackgroundTasks, Service, SchedulerInterface):

    def __init__(self, configService: ConfigService, redisService: RedisService):
        self.configService = configService
        self.redisService = redisService
        self.running_background_tasks_count = 0
        self.running_route_handler = 0
        self.sharing_task: dict[str, Task] = {}
        self.task_lock = asyncio.Lock()
        self.route_lock = asyncio.Lock()
        self.server_load: dict[TaskHeaviness, int] = {
            t: 0 for t in TaskHeaviness._value2member_map_.values()}
        super().__init__(None)
        Service.__init__(self)

    def _register_tasks(self, request_id: str):
        self.sharing_task[request_id] = {
            'meta':{},
            'taskConfig':[]
        }

    def _delete_tasks(self, request_id: str):
        try:
            del self.sharing_task[request_id]
        except:
            ...

    async def add_async_task(self, heaviness: TaskHeaviness, task: Coroutine[Any, Any, None], request_id: str, save_result: bool, ttl: int | None,running_type='concurrent'):
        return await self._create_task_(heaviness, task, request_id, save_result, ttl,running_type)

    async def _create_task_(self, heaviness, task, request_id, save_result, ttl,running_type:RunType='concurrent'):
        now = str(dt.datetime.now())
        ttd = self._compute_ttd()
        async with self.task_lock:
            self.server_load[heaviness] += 1
            self.running_background_tasks_count+=1

        if isinstance(task, BackgroundTask):
            name = task.func.__qualname__
        else:
            name = task.__qualname__
        self.sharing_task[request_id]['taskConfig'].append(TaskConfig(
            task=task,
            heaviness=heaviness,
            save_result=save_result,
            ttl=ttl,
            ttd=ttd,
            running_type=running_type
        ))
        return {'date': now,
                'message': f"[{name}] - Task added successfully", 'heaviness': str(heaviness), 'handler': 'BackgroundTask', 'estimate_tbd': naturaldelta(ttd),
                'request_id': request_id}

    async def add_task(self, heaviness: TaskHeaviness, request_id: str, save_result: bool, ttl: int | None,running_type:RunType, func: typing.Callable[P, typing.Any], *args: P.args, **kwargs: P.kwargs):
        task = BackgroundTask(func, *args, **kwargs)
        return await self._create_task_(heaviness, task, request_id, save_result, ttl)

    def build(self):
        try:
            self.connection_count = Gauge('http_connections','Active Connection Count')
            self.request_latency = Histogram("http_request_duration_seconds", "Request duration in seconds")
        except:
            raise BuildWarningError


    def _compute_ttd(self,):
        return 0

    @property
    async def global_task_count(self):
        async with self.task_lock:
            return self.running_background_tasks_count

    @property    
    async def global_route_handler_count(self):
        async with self.route_lock:
            return self.running_route_handler

    def __call__(self, request_id: str) -> None:
        meta = self.sharing_task[request_id]['meta']
        schedule= lambda: asyncio.create_task(self._run_task_in_background(request_id))
        #self.schedule(0,1,action=schedule)
        schedule()

    async def _run_task_in_background(self, request_id):
        task_len = len(self.sharing_task['taskConfig'][request_id])
        for i, t in enumerate(self.sharing_task['taskConfig'][request_id]):
            task = t['task']
            heaviness_ = t['heaviness']
            ttd = t['ttd']
            runType = t['running_type']
            if ttd and ttd>0:
                await asyncio.sleep(ttd)

            is_saving_result = t['save_result']
            data=None if runType == 'parallel' else []

            async def callback():
                try:
                    if not asyncio.iscoroutine(task):
                        result = await task()
                    else:
                        result = await task
                    if is_saving_result:
                        if runType == 'concurrent':
                            data.append(result)
                        else:
                            await self.redisService.store_bkg_result(result, request_id)
                    
                    if runType=='parallel':
                        async with self.task_lock:
                            self.running_background_tasks_count -= 1  # Decrease count after tasks complete
                            self.server_load[heaviness_] -= 1
                
                    return result
                except Exception as e:
                    result = {
                        'error_class':e.__class__,
                        'args':str(e.args)
                    }
                    if is_saving_result:
                        if runType == 'concurrent':
                            data.append(result)
                        else:
                            await self.redisService.store_bkg_result(result, request_id)
                    
                    if runType =='parallel':
                        async with self.task_lock:
                            self.running_background_tasks_count -= 1  # Decrease count after tasks complete
                            self.server_load[heaviness_] -= 1
                    return result

            if runType=='concurrent':
                await callback()
            else:
                asyncio.create_task(callback)

        if runType  == 'concurrent':
            await self.redisService.store_bkg_result(data, request_id)
            async with self.task_lock:
                self.running_background_tasks_count -= task_len  # Decrease count after tasks complete
                self.server_load[heaviness_] -= 1

        self._delete_tasks(request_id)

    async def pingService(self, count=None):  # TODO
        response_count = await self.global_task_count
        load = self.server_load.copy()

        self.check_system_ram()
        if count:
            ...

        return await Service.pingService(self)

    def check_system_ram():
        ...

    def populate_response_with_request_id(self, request: Request, response: Response):
        response.headers.append(
            HTTPHeaderConstant.REQUEST_ID, request.state.request_id)


@ServiceClass
class CeleryService(Service, IntervalInterface):
    _celery_app = celery_app
    _task_registry = TASK_REGISTRY

    def __init__(self, configService: ConfigService, bTaskService: TaskService):
        Service.__init__(self)
        IntervalInterface.__init__(self)
        self.configService = configService
        self.bTaskService = bTaskService
        self.available_workers_count = -1
        self.worker_not_available_count = 0

        self.timeout_count = 0
        self.task_lock = asyncio.Lock()

        # self.redis_client = Redis(host='localhost', port=6379, db=0)# set from config

    def trigger_task_from_scheduler(self, scheduler: SchedulerModel, *args, **kwargs):
        celery_task = scheduler.model_dump(mode='python', exclude={'content'})
        celery_task: CeleryTask = CeleryTask(
            args=args, kwargs=kwargs, **celery_task)
        return self._trigger_task(celery_task, scheduler.schedule_name)

    def trigger_task_from_task(self, celery_task: CeleryTask, schedule_name: str = None):
        return self._trigger_task(celery_task, schedule_name)

    def _trigger_task(self, celery_task: CeleryTask, schedule_name: str = None):
        schedule_id = schedule_name if schedule_name is not None else generateId(
            25)
        c_type = celery_task['task_type']
        t_name = celery_task['task_name']
        now = dt.datetime.now()
        result = {'data': now,
                  'message': f'Task [{t_name}] received successfully', 'heaviness': celery_task['heaviness'], 'handler': 'Redis'}

        if c_type == 'now':
            task_result = self._task_registry[t_name]['task'].delay(
                *celery_task['args'], **celery_task['kwargs'])
            result.update({'task_id': task_result.id, 'type': 'task'})
            return result

        options = celery_task['task_option']
        if c_type == 'once':
            task_result = self._task_registry[t_name]['task'].apply_async(
                **options, args=celery_task['args'], kwargs=celery_task['kwargs'])
            result.update({'task_id': task_result.id, 'type': 'task'})
            return result

        schedule = SCHEDULER_RULES[c_type]
        try:
            schedule = schedule(**options)  # ERROR
        except ValueError:
            raise CelerySchedulerOptionError

        entry = RedBeatSchedulerEntry(
            schedule_id, t_name, schedule, args=celery_task['args'], kwargs=celery_task['kwargs'], app=self._celery_app)
        entry.save()
        result.update({'task_id': schedule_id, 'type': 'schedule'})
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
            entry = RedBeatSchedulerEntry.from_key(
                schedule_id, app=self._celery_app)
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

    def manually_set_task_expires_result(self, expires: int, scheduler: SchedulerModel):
        raise NotImplementedError
        if scheduler.task_type == 'now':
            self.redis_client.expire(
                f'celery-task-meta-{scheduler.task_name}', 3600)  # Expire in 1 hour

    def build(self):
        ...

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
                self.service_status = ServiceStatus.TEMPORARY_NOT_AVAILABLE
                async with self.task_lock:
                    self.available_workers_count = 0

            async with self.task_lock:
                self.available_workers_count = available_workers_count
            self.worker_not_available = self.configService.CELERY_WORKERS_COUNT - \
                available_workers_count
            self.timeout_count = 0
        except Exception as e:
            self.timeout_count += 1
            async with self.task_lock:
                self.available_workers_count = 0

    @property
    async def get_available_workers_count(self) -> float:
        async with self.task_lock:
            return self.available_workers_count

    async def pingService(self, ratio: float = None, count: int = None):
        response_count = await self.get_available_workers_count
        if ratio:
            # TODO check in which interval the ratio is in
            ...
        if count:
            # TODO check in which interval the ratio is in
            ...
        await super().pingService()
        return response_count, response_count/self.configService.CELERY_WORKERS_COUNT

    def callback(self):
        asyncio.create_task(self._check_workers_status())


@ServiceClass
class OffloadTaskService(Service):

    Algorithm = Literal['normal', 'worker_focus']

    def __init__(self, configService: ConfigService, celeryService: CeleryService, taskService: TaskService):
        super().__init__()
        self.configService = configService
        self.celeryService = celeryService
        self.taskService = taskService

    def build(self):
        ...

    async def offload_task(self, algorithm: Algorithm, scheduler: SchedulerModel, save_result: bool, ttl: int, x_request_id: str, as_async: bool,runType:RunType, callback: Callable, *args, **kwargs):
        # TODO choose algorightm
        if algorithm == 'normal':
            ...
        return await self._normal_offload(scheduler, save_result, ttl, x_request_id, as_async, callback, *args, **kwargs)

    async def _normal_offload(self, scheduler: SchedulerModel, save_result: bool, ttl: int, x_request_id: str, as_async: bool,runType:RunType, callback: Callable, *args, **kwargs):
        # TODO check celery worker,
        if scheduler.task_type == TaskType.NOW.value:
            if as_async:
                return await self.taskService.add_task(scheduler.heaviness, x_request_id, save_result, ttl,runType, callback, *args, **kwargs)
            else:
                return callback(*args, **kwargs)
        return self.celeryService.trigger_task_from_scheduler(scheduler, *args, **kwargs)
