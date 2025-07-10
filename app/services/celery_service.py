import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Literal, ParamSpec, TypedDict
import typing
from app.classes.celery import CelerySchedulerOptionError, CeleryTaskNotFoundError, SCHEDULER_RULES, TaskRetryError, TaskHeaviness, TaskType, s
from app.classes.celery import CeleryTask, SchedulerModel
from app.definition._service import BuildFailureError, BaseService, Service, ServiceStatus,BuildWarningError
from app.interface.timers import IntervalInterface, SchedulerInterface
from app.services.database_service import RedisService
from app.utils.constant import HTTPHeaderConstant, StreamConstant
from app.utils.transformer import none_to_empty_str
from .config_service import ConfigService
from app.utils.helper import flatten_dict, generateId
from app.task import TASK_REGISTRY, celery_app, AsyncResult, task_name
from redbeat import RedBeatSchedulerEntry
from app.utils.helper import generateId
import datetime as dt
from fastapi import BackgroundTasks, Request, Response
from starlette.background import BackgroundTask
from humanize import naturaltime, naturaldelta
from prometheus_client import Counter,Histogram,Gauge
from random import randint
from dataclasses import field
from aiorwlock import RWLock


P = ParamSpec("P")
RunType = Literal['parallel','sequential']
Algorithm = Literal['normal', 'worker_focus','route-focus']


class TaskConfig(TypedDict):
    task: BackgroundTask | Coroutine
    scheduler: SchedulerModel |s 
    delay: float

class TaskMeta(TypedDict):
    x_request_id:str
    as_async:bool
    runtype:RunType
    save_result:bool
    retry:bool
    ttl:float=3600 # time to live in the redis database
    ttd:float=0
    tt:float = 0 

@dataclass        
class TaskManager():
    meta: TaskMeta
    offloadTask: Callable
    return_results:bool
    taskConfig: list[TaskConfig] = field(default_factory=list)
    task_result: list[dict] = field(default_factory=list)

    async def offload_task(self, algorithm: Algorithm, scheduler: SchedulerModel, delay: float, index: int | None, callback: Callable, *args, **kwargs):
        values = await self.offloadTask(algorithm, scheduler, delay,self.meta['retry'] ,self.meta['x_request_id'], self.meta['as_async'], index, callback, *args, **kwargs)
        self.task_result.append(values)

    def append_taskConfig(self,task,scheduler,delay):

        if len(self.taskConfig)==0:
            self.meta['ttd'] +=delay

        self.meta['tt']+=delay
        new_delay = self.meta['tt']
        self.taskConfig.append(TaskConfig(
            task=task,
            scheduler=scheduler,
            delay=delay,
        ))

        return new_delay

    @property
    def results(self):
        if not self.return_results:
            return {}
        meta = self.meta.copy()
        meta['ttd'] = naturaldelta(meta['ttd'])
        meta.pop('tt',None)
        return {
            'meta': meta,
            'results': self.task_result,
            'errors':self.errors
        }
    
    @property
    def errors(self):
        if len(self.taskConfig) == 0:
            return {}
        elif isinstance(self.taskConfig[0]['scheduler'],s):
            return {}
        else:
            return self.taskConfig[0]['scheduler']._errors

    @property
    def schedule_ttd(self):
        return self.meta['ttd'] - self.taskConfig[0]['delay']

@Service
class CeleryService(BaseService, IntervalInterface):
    _celery_app = celery_app
    _task_registry = TASK_REGISTRY

    def __init__(self, configService: ConfigService,redisService:RedisService):
        BaseService.__init__(self)
        IntervalInterface.__init__(self,False)
        self.configService = configService

        self.redisService = redisService
        self.available_workers_count = -1
        self.worker_not_available_count = 0

        self.timeout_count = 0
        self.task_lock = RWLock()
        # NOTE if i cant connect to the redis server there's a problem, if i can connect i can add task to the message broker

        # self.redis_client = Redis(host='localhost', port=6379, db=0)# set from config

    def trigger_task_from_scheduler(self, scheduler: SchedulerModel,index:int|None, *args, **kwargs):
        params = self.scheduler_to_celery_task(scheduler,index,*args,**kwargs)
        return self._trigger_task(**params)

    def trigger_task_from_task(self, celery_task: CeleryTask,index:int|None, schedule_name: str = None):
        return self._trigger_task(celery_task, schedule_name,index)

    def scheduler_to_celery_task(self,scheduler: SchedulerModel,index:int|None, *args, **kwargs):
        celery_task = scheduler.model_dump(mode='python', exclude={'content','sender_type','filter_error'})
        celery_task: CeleryTask = CeleryTask(args=args, kwargs=kwargs, **celery_task)
        return {
            'celery_task':celery_task,
            'index':index,
            'schedule_name':scheduler.schedule_name
        }

    def _trigger_task(self, celery_task: CeleryTask, schedule_name: str = None,index:int|None=None):
        schedule_id = schedule_name if schedule_name is not None else generateId(
            25)
        c_type = celery_task['task_type']
        t_name = celery_task['task_name']
        now = dt.datetime.now()
        now = str(now)
        result = {
            'date': now,
            'offloaded':True,
                  'index':index,
                  'message': f'Task [{t_name}] received successfully', 'heaviness': str(celery_task['heaviness']), 'handler': 'Celery','expected_tbd':naturaldelta(0)}

        if c_type == 'now':
            task_result = self._task_registry[t_name]['task'].delay(*celery_task['args'], **celery_task['kwargs'])
            result.update({'task_id': task_result.id, 'type': 'task'})
            return result

        options = celery_task['task_option']
        if c_type == 'once':
            task_result = self._task_registry[t_name]['task'].apply_async(**options, args=celery_task['args'], kwargs=celery_task['kwargs'])
            
            eta = options.get('eta') or (dt.datetime.now() + dt.timedelta(seconds=options.get('countdown', 0)))
            time_until_first_run = (eta - dt.datetime.now()).total_seconds() if eta else None
            
            result.update({'task_id': task_result.id, 'type': 'task', 'expected_tbd': naturaldelta(time_until_first_run) if time_until_first_run else None})

            return result

        schedule = SCHEDULER_RULES[c_type]
        try:
            schedule = schedule(**options)  # ERROR
        except ValueError:
            raise CelerySchedulerOptionError

        entry = RedBeatSchedulerEntry(
            schedule_id, t_name, schedule, args=celery_task['args'], kwargs=celery_task['kwargs'], app=self._celery_app)
        entry.save()
        if isinstance(entry.due_at,dt.datetime):
            time =entry.due_at.utcoffset().seconds
        elif isinstance(entry.due_at,(float,int)):
            time = entry.due_at
        else:
            time = None
            
        result.update({'task_id': schedule_id, 'type': 'schedule','expected_tbd':None if time == None else naturaldelta(time)})
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
        if self.redisService.service_status == ServiceStatus.NOT_AVAILABLE:
            raise BuildFailureError

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
                async with self.task_lock.writer:
                    self.available_workers_count = 0

            async with self.task_lock.reader:
                self.available_workers_count = available_workers_count
            self.worker_not_available = self.configService.CELERY_WORKERS_COUNT - \
                available_workers_count
            self.timeout_count = 0
        except Exception as e:
            self.timeout_count += 1
            async with self.task_lock.writer:
                self.available_workers_count = 0

    @property
    async def get_available_workers_count(self) -> float:
        async with self.task_lock.reader:
            return self.available_workers_count

    async def async_pingService(self, ratio: float = None, count: int = None):
        response_count = await self.get_available_workers_count
        if ratio:
            # TODO check in which interval the ratio is in
            ...
        if count:
            # TODO check in which interval the ratio is in
            ...
        await BaseService.async_pingService(self)
        return response_count, response_count/self.configService.CELERY_WORKERS_COUNT

    def callback(self):
        asyncio.create_task(self._check_workers_status())

@Service
class TaskService(BackgroundTasks, BaseService, SchedulerInterface):

    def __init__(self, configService: ConfigService, celeryService:CeleryService, redisService: RedisService):
        self.configService = configService
        self.redisService = redisService
        self.celeryService = celeryService

        self.running_background_tasks_count = 0
        self.running_route_handler = 0
        self.sharing_task: dict[str, TaskManager] = {}
        self.task_lock = RWLock()
        self.route_lock = RWLock()
        self.server_load: dict[TaskHeaviness, int] = {
            t: 0 for t in TaskHeaviness._value2member_map_.values()}
        
        super().__init__(None)
        BaseService.__init__(self)
        SchedulerInterface.__init__(self)

    def _register_tasks(self, request_id: str,as_async:bool,runtype:RunType,offloadTask:Callable,ttl:int,save_results:bool,return_results:bool,retry:bool)->TaskManager:
        meta = TaskMeta(x_request_id=request_id,as_async=as_async,runtype=runtype,save_result=save_results,ttl=ttl,tt=0,ttd=0,retry=retry)
        task = TaskManager(meta=meta,offloadTask=offloadTask,return_results=return_results)
        self.sharing_task[request_id] = task
        return task

    def _delete_tasks(self, request_id: str):
        try:
            del self.sharing_task[request_id]
        except:
            ...

    async def run_task_in_route_handler(self,scheduler:SchedulerModel|s,is_retry:bool,index,callback,*args,**kwargs):
        now = dt.datetime.now().isoformat()
        try:
            if asyncio.iscoroutine(callback):
                result = await callback
            elif asyncio.iscoroutinefunction(callback):
                result =  await callback(*args,**kwargs)
            else:    
                result = callback(*args, **kwargs)

            return {
                'handler':'Route Handler',
                'offloaded':True,
                'date':now,
                'expected_tbd':'now',
                'index':index,
                'result':result
            }
        except TaskRetryError as e:
            if is_retry:
                if not isinstance(scheduler,s):
                    params = self.celeryService.scheduler_to_celery_task(scheduler,index,*args,**kwargs)
                    params = flatten_dict(params,serialized=True)
                    await self.redisService.stream_data(StreamConstant.CELERY_RETRY_MECHANISM,params)
            return {
                'handler':'Route Handler',
                'offloaded':True,
                'date':now,
                'index':index,
                'result':None,
                'error':True
            }

    async def add_task(self, scheduler:SchedulerModel |s , request_id: str,delay:float|None,index,func: typing.Callable[P, typing.Any], *args: P.args, **kwargs: P.kwargs):
        task = BackgroundTask(func, *args, **kwargs)
        return await self._create_task_(scheduler, task, request_id,delay,index,)

    async def add_async_task(self, scheduler: SchedulerModel |s, request_id: str,delay:int|None,index,task: Coroutine[Any, Any, None]):
        return await self._create_task_(scheduler, task, request_id,delay,index)

    async def _create_task_(self, scheduler:SchedulerModel |s, task, request_id:str,delay:float,index):
        now = dt.datetime.now().isoformat()
        async with self.task_lock:
            self.server_load[scheduler.heaviness] += 1
            self.running_background_tasks_count+=1

        #delay = self._compute_ttd()

        if isinstance(task, BackgroundTask):
            name = task.func.__qualname__
        else:
            name = task.__qualname__

        new_delay = self.sharing_task[request_id].append_taskConfig(task,scheduler,delay)
        
        return {
            'date': now,'handler': 'BackgroundTask',
            'task_id':request_id,
            'offloaded':True,
            'index':index,
                'message': f"[{name}] - Task added successfully", 'heaviness': str(scheduler.heaviness), 'estimate_tbd': naturaldelta(new_delay),}

    def build(self):
        try:
            self.connection_count = Gauge('http_connections','Active Connection Count')
            self.request_latency = Histogram("http_request_duration_seconds", "Request duration in seconds")
            self.connection_total = Counter('total_http_connections','Total Request Received')
            self.background_task_count = Gauge('background_task','Active Background Working Task')
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

    async def __call__(self, request_id: str) -> None:
        taskManager = self.sharing_task[request_id]
        meta = taskManager.meta
        #schedule= lambda: asyncio.create_task(self._run_task_in_background(request_id))
        random_ttd = randint(0, 60)
        #print(f"Scheduled task with a random delay of {random_delay} seconds")
        #self.schedule(random_delay,action=schedule) # FIXME later 
        return await self._run_task_in_background(request_id)
        #schedule()

    async def _run_task_in_background(self, request_id):
        task_config = self.sharing_task[request_id].taskConfig
        task_len = len(task_config)

        meta = self.sharing_task[request_id].meta
        ttl=meta['ttl']
        is_saving_result = meta['save_result']
        runType = meta['runtype']
        is_retry = meta['retry']

        for i, t in enumerate(task_config):  # TODO add the index i to the results
            task:BackgroundTask = t['task']
            heaviness_ = t['scheduler'].heaviness
            scheduler = t['scheduler']
            delay = t['delay']
            if delay and delay>0:
                await asyncio.sleep(delay)

            data=None if runType == 'parallel' else []
            self.background_task_count.inc()
           
            async def callback():

                async def parse_error(e:Exception,bypass=False):
                    result = {
                        'error_class':e.__class__,
                        'args':str(e.args)
                    }
                    if bypass:
                        result['bypass']=True
                    if is_saving_result:
                        if runType == 'sequential':
                            data.append(result)
                        else:
                            await self.redisService.store_bkg_result(result, request_id,ttl)
                    
                    if runType =='parallel':
                        async with self.task_lock:
                            self.running_background_tasks_count -= 1  # Decrease count after tasks complete
                            self.server_load[heaviness_] -= 1 # TODO better estimate
                        self.background_task_count.dec()
                        
                    return result

                try:
                    if not asyncio.iscoroutine(task):
                        result = await task()
                    else:
                        result = await task
                    if is_saving_result:
                        if runType == 'sequential':
                            data.append(result)
                        else:
                            await self.redisService.store_bkg_result(result, request_id,ttl)
                    
                    if runType=='parallel':
                        async with self.task_lock:
                            self.running_background_tasks_count -= 1  # Decrease count after tasks complete
                            self.server_load[heaviness_] -= 1 # TODO better estimate
                        self.background_task_count.dec()

                
                    return result
                except TaskRetryError as e:
                    error = e.error
                    if is_retry:
                        if not isinstance(scheduler,s) and isinstance(task,BackgroundTask):
                            params = self.celeryService.scheduler_to_celery_task(scheduler,i,task.args,task.kwargs)
                            params = flatten_dict(params,serialized=True)
                            await self.redisService.stream_data(StreamConstant.CELERY_RETRY_MECHANISM,params)
                            return
                        
                        return await parse_error(error,True)
                        
                    return await parse_error(error)
                except Exception as e:
                    return await parse_error(e)
    
            if runType=='sequential': 
                await callback()
            else:
                asyncio.create_task(callback())

        if runType == 'sequential':
            await self.redisService.store_bkg_result(data, request_id,ttl)
            async with self.task_lock:
                self.running_background_tasks_count -= task_len  # Decrease count after tasks complete
                self.server_load[heaviness_] -= 1 # TODO better estimate
            self.background_task_count.dec(task_len)
            
        self._delete_tasks(request_id)

    async def async_pingService(self, count=None):  # TODO
        response_count = await self.global_task_count
        load = self.server_load.copy()

        self.check_system_ram()
        if count:
            ...

        return await BaseService.async_pingService(self)

    def check_system_ram():
        ...

    def populate_response_with_request_id(self, request: Request, response: Response):
        response.headers.append(HTTPHeaderConstant.REQUEST_ID, request.state.request_id)

@Service
class OffloadTaskService(BaseService):

    def __init__(self, configService: ConfigService, celeryService: CeleryService, taskService: TaskService):
        super().__init__()
        self.configService = configService
        self.celeryService = celeryService
        self.taskService = taskService

    def build(self):
        ...

    async def offload_task(self, algorithm: Algorithm, scheduler: SchedulerModel|s,delay: float,is_retry:bool, x_request_id: str, as_async: bool, index,callback: Callable, *args, **kwargs):
        # TODO choose algorightm
        if algorithm == 'normal':
             return await self._normal_offload(scheduler, delay,is_retry, x_request_id, as_async,index,callback, *args, **kwargs)
        if algorithm == 'worker_focus':
            return self.celeryService.trigger_task_from_scheduler(scheduler,index, *args, **kwargs)
            
        if algorithm == 'route-focus':
            return await self._route_offload(scheduler, delay,is_retry, x_request_id, as_async,index,callback, *args, **kwargs)

    async def _normal_offload(self, scheduler: SchedulerModel|s, delay: float,is_retry:bool, x_request_id: str, as_async: bool,index, callback: Callable, *args, **kwargs):
        # TODO check celery worker,
        if scheduler.task_type == TaskType.NOW.value:
            if as_async:
                if asyncio.iscoroutine(callback):
                    return await self.taskService.add_async_task(scheduler,x_request_id,delay,index,callback)
                return await self.taskService.add_task(scheduler, x_request_id, delay, index,callback, *args, **kwargs)
            
            else:
                return await self.taskService.run_task_in_route_handler(scheduler,is_retry,index,callback,*args,**kwargs)
                

        return self.celeryService.trigger_task_from_scheduler(scheduler,index, *args, **kwargs)


    async def _route_offload(self,scheduler,delay: float,is_retry:bool, x_request_id: str, as_async: bool, index,callback: Callable, *args, **kwargs):
        if as_async:
            if asyncio.iscoroutine(callback):
                return await self.taskService.add_async_task(scheduler,x_request_id,delay,index,callback)
            return await self.taskService.add_task(scheduler, x_request_id, delay, index,callback, *args, **kwargs)
            
        else:
                return await self.taskService.run_task_in_route_handler(scheduler,is_retry,index,callback,*args,**kwargs)