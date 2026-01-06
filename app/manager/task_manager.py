import asyncio
from dataclasses import asdict
from typing import Any, Coroutine, Literal, ParamSpec, TypedDict
from fastapi import Depends
from humanize import naturaldelta
from app.classes.celery import FALLBACK_ENV_TASK, AlgorithmType, Compute_Weight, SchedulerModel, TaskExecutionResult, TaskRetryError, TaskType, add_messages, s
from app.classes.env_selector import DEFAULT_MASK, EnvSelection, StrategyType, compute_p_values, get_selector
from app.definition._service import ServiceStatus
from app.depends.dependencies import get_request_id
from starlette.background import BackgroundTask,BackgroundTasks
from app.depends.variables import *
import datetime as dt
from app.container import Get
from app.services.worker.celery_service import CeleryService,TASK_REGISTRY
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from app.services.monitoring_service import MonitoringService
from app.services.worker.task_service import TaskService
from app.utils.tools import RunInThreadPool
from app.utils.constant import APSchedulerConstant, MonitorConstant, RedisConstant,CeleryConstant

P = ParamSpec("P")

class TaskConfig(TypedDict):
    task: BackgroundTask | Coroutine
    delay: float

class TaskMeta(TypedDict):
    request_id:str
    fallback:bool
    background:bool
    algorithm:AlgorithmType
    strategy:StrategyType
    runtype: RunType
    save_result:bool
    split:bool
    retry:bool
    ttl:float=3600 # time to live in the redis database
    ttd:float=0
    tt:float = 0 

class TaskManager:
    
    _mask_schedule:list[EnvSelection] = [0,1,1,0]
    _not_allowed_aps_task_type: set[TaskType] = {TaskType.RRULE,TaskType.SOLAR}

    def __init__(self,backgroundTasks:BackgroundTasks,response:Response,request:Request,request_id: str = Depends(get_request_id), background: bool = Depends(background_query), runtype: RunType = Depends(runtype_query), ttl=Query(1, ge=0, le=24*60*60), save_results:bool=Depends(save_results_query), return_results:bool=Depends(get_task_results),retry:bool=Depends(retry_query),split:bool = Depends(split_query),algorithm:AlgorithmType = Depends(algorithm_query),strategy:StrategyType = Depends(strategy_query),fallback:bool=Depends(fallback_query)):
        self.return_results:bool = return_results
        self.backgroundTasks = backgroundTasks
        self.response = response
        self.request = request

        self.taskConfig: list[TaskConfig] = []
        self.weight = 0.0
        self.scheduler: SchedulerModel = None
        self.task_result:list[TaskExecutionResult] = []
        self.meta: TaskMeta = TaskMeta(request_id=request_id,background=background,runtype=runtype,save_result=save_results,ttl=ttl,tt=0,ttd=0,retry=retry,split=split,algorithm=algorithm,strategy=strategy,fallback=fallback)

        self.celeryService = Get(CeleryService)
        self.configService = Get(ConfigService)
        self.taskService = Get(TaskService)
        self.redisService = Get(RedisService)
        self.monitoringService = Get(MonitoringService)
    
    @staticmethod
    def parse_error(e:Exception,bypass=False,retry=None):
        r = {'error_class':e.__class__,'args':str(e.args)}
        if bypass:
            r['bypass']=True
        if retry:
            r['retry'] = retry
        return r

    def set_algorithm(self, algorithm: AlgorithmType):
        if algorithm not in get_args(AlgorithmType):
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        self.meta['algorithm'] = algorithm

    def register_scheduler(self, scheduler: SchedulerModel):
        if not isinstance(scheduler, SchedulerModel):
            raise TypeError("Scheduler must be an instance of SchedulerModel")
        self.scheduler = scheduler

    def append_taskConfig(self,task,delay):

        if len(self.taskConfig)==0:
            self.meta['ttd'] +=delay

        self.meta['tt']+=delay
        new_delay = self.meta['tt']
        self.taskConfig.append(TaskConfig(
            task=task,
            delay=delay,
        ))

        return new_delay

    async def offload_task(self,weight:float,delay: float, index: int | None, callback: Callable, *args,_s:s|None=None, **kwargs):
        scheduler = self.scheduler if _s is None else _s
        weight = Compute_Weight(weight, scheduler._heaviness)
        values:TaskExecutionResult = await self._offload_task(weight,delay,index, callback, *args, **kwargs)
        self.task_result.append(asdict(values))
        self.weight +=weight

    async def add_task(self, delay:float|None,index,callback: Callable[P, Any], *args: P.args, **kwargs: P.kwargs):
        task = callback if asyncio.iscoroutine(callback) else BackgroundTask(callback, *args, **kwargs)
        now = dt.datetime.now().isoformat()
        name = task.func.__qualname__ if isinstance(task, BackgroundTask) else task.__qualname__
        new_delay = self.append_taskConfig(task,delay)
        return TaskExecutionResult(True,now,'BackgroundTask',naturaldelta(new_delay),index,str(self.scheduler._heaviness),None,task_id= self.meta['request_id'],message=f"[{name}] - Task added successfully" )
    
    async def select_task_env(self,task_weight:float,needed_envs:list[Literal[0,1]]=DEFAULT_MASK)->EnvSelection:
        current_workers_count = len(self.celeryService._workers)
        p1,p2,p3 = compute_p_values(current_workers_count,self.configService.CELERY_WORKERS_EXPECTED,task_weight)
        return get_selector(self.meta['strategy'],celery_broker=self.configService.BROKER_PROVIDER).select(p1, p2, p3,needed_envs)

    def register_backgroundTask(self):
        callbacks = []
        for callback in self._create_background_tasks():
            async def wrapper():
                await asyncio.sleep(0.1)
                await callback()
            if self.meta['runtype'] == 'sequential':
                self.backgroundTasks.add_task(wrapper)

        if self.meta['runtype'] == 'sequential':
            return
        
        async def gather_wrapper():
            await asyncio.sleep(0.1)
            await asyncio.gather(*callbacks,return_exceptions=True)

        self.backgroundTasks.add_task(gather_wrapper)

    @property
    def results(self):
        if not self.return_results:
            return {}
        meta = self.meta.copy()
        meta['ttd'] = naturaldelta(meta['ttd'])
        meta.pop('tt',None)
        return {
            'meta': meta,
            'weight': self.weight,
            'results': self.task_result,
            'errors':self.scheduler._errors if self.scheduler else {},
            'messages': self.scheduler._messages if self.scheduler else [],
            'warnings': self.scheduler._warnings if self.scheduler else []
        }

    @property
    def schedule_ttd(self):
        return self.meta['ttd'] - self.taskConfig[0]['delay']
        
    def _create_background_tasks(self):
        delay = t['delay']
        to_retry = self.meta['retry']

        for i, t in enumerate(self.taskConfig):  # TODO add the index i to the results
            task:BackgroundTask = t['task']
            
            async def callback():
                if delay and delay>0:
                    await asyncio.sleep(delay)
                self.monitoringService.gauge_inc(MonitorConstant.BACKGROUND_TASK_COUNT)
                try:
                    result= await task() if not asyncio.iscoroutine(task) else await task                    
                except TaskRetryError as e:
                    error = e.error
                    bypass =True
                    if to_retry and isinstance(self.scheduler,s) and isinstance(task,BackgroundTask):
                        retry_result = await self.celeryService.trigger_task_from_scheduler(self.scheduler,i,*task.args,**task.kwargs)
                        bypass = False
                    result= self.parse_error(error,bypass,retry_result if not bypass else None)
                except Exception as e:
                    result = self.parse_error(e)
                finally:
                    if self.meta['save_result']:
                        await self.store_bkg_result(result, self.meta['request_id'],self.meta['ttl'],f"{i}")
                    self.monitoringService.gauge_dec(MonitorConstant.BACKGROUND_TASK_COUNT)

            yield callback
        

    async def _offload_task(self,weight: float,delay: float,index:int,callback: Callable, *args, **kwargs)->TaskExecutionResult:
        """
        - RRule and Solar Task Type are rejected if theres no expected workers
        - If theres no worker and no aps scheduler schedule type are rejected
        """
        algorithm = self.meta['algorithm']
        now = dt.datetime.now().isoformat()
        from_handler_error = None
        
        while True:
            match algorithm:
                case  'normal':
                    return await self._normal_offload(weight,delay,index,callback, *args, **kwargs)
                
                case 'worker':
                    if self.configService.CELERY_WORKERS_EXPECTED >= 1:
                        return await self.celeryService.trigger_task_from_scheduler(self.scheduler,index,weight,*args, **kwargs)
                    elif self.taskService.service_status == ServiceStatus.AVAILABLE:
                        algorithm = 'aps'
                        add_messages(FALLBACK_ENV_TASK, self.scheduler, index=index,obj='aps')
                    elif self.scheduler.task_type == TaskType.NOW:
                        algorithm = 'route'
                        add_messages(FALLBACK_ENV_TASK, self.scheduler, index=index,obj='route')
                    else:
                        add_messages()
                        algorithm='error'
                        from_handler_error = 'Celery'

                case 'route':
                    if  isinstance(self.scheduler, SchedulerModel) and self.scheduler.task_type != TaskType.NOW:
                        algorithm = 'worker'
                        add_messages(FALLBACK_ENV_TASK, self.scheduler, index=index,obj='celery worker')
                        continue

                    return await self._route_offload(None,weight,delay,index,callback, *args, **kwargs)
                
                case 'mix':
                    return await self._mix_offload(weight,delay,index,callback, *args, **kwargs)
                
                case 'aps':
                    if self.configService.APS_ACTIVATED:
                        return await self._schedule_aps_task(weight,delay,index,callback,*args,**kwargs)
                    elif self.configService.CELERY_WORKERS_EXPECTED >=1:
                        algorithm = 'worker'
                        add_messages(FALLBACK_ENV_TASK, self.scheduler, index=index,obj='celery worker')
                    elif self.scheduler.task_type == TaskType.NOW:
                        algorithm = 'route'
                        add_messages(FALLBACK_ENV_TASK, self.scheduler, index=index,obj='route')
                    else:
                        algorithm = 'error'
                        from_handler_error = 'APScheduler'
                case "error":
                    add_messages()
                    return TaskExecutionResult(False,now,from_handler_error,None,index,None,None,True,self.meta['request_id'],'schedule','Was not able to fallback to other task scheduler provider')
                case _:
                    return TaskExecutionResult(False,now,'RouteHandler',None,index,None,None,True,self.meta['task_id'],None,message=f'Algorithm not supported {algorithm}')

    async def _normal_offload(self,weight:float, delay: float,index:int, callback: Callable, *args, **kwargs)->TaskExecutionResult:
        if self.scheduler.task_type == TaskType.NOW:
            return await self._route_offload(None,weight,delay,index,callback,*args,**kwargs)
        elif self.configService.CELERY_WORKERS_EXPECTED >= 1:
            return  await self.celeryService.trigger_task_from_scheduler(self.scheduler,index,weight, *args, **kwargs)
        else:
            return await self._schedule_aps_task(weight,delay,index,callback,*args,**kwargs)

    async def _route_offload(self,from_env:EnvSelection|None,weight:float,delay: float,index,callback: Callable, *args, **kwargs)->TaskExecutionResult:
        background =  self.meta.get('background',True)
        if background or (from_env and from_env == 'routebkg'):
            return await self.add_task(delay, index,callback, *args, **kwargs)
        else:
            now = dt.datetime.now().isoformat()
            try:
                if asyncio.iscoroutine(callback):
                    result = await callback
                elif asyncio.iscoroutinefunction(callback):
                    result =  await callback(*args,**kwargs)
                else:    
                    result = callback(*args, **kwargs)

                return TaskExecutionResult(handler='Route Handler',offloaded=False,date=now,expected_tbd='now',index=index,result=result,heaviness=str(self.scheduler._heaviness))
            except TaskRetryError as e:
                if self.meta['is_retry']:
                    if not isinstance(self.scheduler,s):
                        await self.celeryService.trigger_task_from_scheduler(self.scheduler,index,weight,*args, **kwargs)
                return TaskExecutionResult(handler='Route Handler',offloaded=True,date=now,index=index,error=True,result=None,heaviness=str(self.scheduler._heaviness))

    async def _mix_offload(self,weight:float,delay,index:int, callback: Callable, *args, **kwargs)->TaskExecutionResult:
        match self.scheduler.task_type:
            case TaskType.NOW:
                mask = [1,int(self.configService.CELERY_WORKERS_EXPECTED >= 1),int(self.taskService.service_status == ServiceStatus.AVAILABLE),1]
                env = await self.select_task_env(weight,mask)
                if env.startswith('route'):
                    return await self._route_offload(env,weight,delay,index,callback,*args,**kwargs)
                elif env == 'worker':
                    return await self.celeryService.trigger_task_from_scheduler(self.scheduler,index,weight, *args, **kwargs)
                else:
                    return await self._schedule_aps_task(weight,delay,index,callback,*args,**kwargs)
            case (TaskType.DATETIME,TaskType.TIMEDELTA,TaskType.INTERVAL,TaskType.CRONTAB):
                if (await self.select_task_env(weight,self._mask_schedule)) == 'worker':
                    return await self.celeryService.trigger_task_from_scheduler(self.scheduler,index,weight, *args, **kwargs)
                else:
                    return await self._schedule_aps_task(weight,delay,index,callback,*args,**kwargs)
            case (TaskType.SOLAR,TaskType.RRULE):
                return await self.celeryService.trigger_task_from_scheduler(self.scheduler,index,weight, *args, **kwargs)
            case _:
                now = dt.datetime.now().isoformat()
                return TaskExecutionResult(False,now,'RouteHandler',None,index,None,error=True,task_id=self.meta['request_id'],type=None,message=f'TaskType not supported by the server: {self.scheduler.task_type}')
            
    @RunInThreadPool
    def _schedule_aps_task(self,weight,delay,index:int,callback:Callable,*args,**kwargs):
        now = dt.datetime.now().isoformat()
        job_id = APSchedulerConstant.REDIS_APS_ID_RESOLVER(self.meta['request_id'],index)
        task = TASK_REGISTRY[self.scheduler.task_name]['raw_task']
        delay += 0 if self.scheduler.task_option.countdown == None else self.scheduler.task_option.countdown
        match self.scheduler.task_type:
            case TaskType.NOW:
                job = self.taskService.now_schedule(delay,task,args,kwargs,job_id)
            case (TaskType.DATETIME,TaskType.TIMEDELTA):
                job = self.taskService.date_schedule(self.scheduler._schedule._aps_object,task,args,kwargs,job_id)
            case TaskType.CRONTAB:
                job = self.taskService.cron_schedule(self.scheduler._schedule._aps_object,task,args,kwargs,job_id)
            case TaskType.INTERVAL:
                job = self.taskService.interval_schedule(self.scheduler._schedule._aps_object,task,args,kwargs,job_id)
            case _:
                return TaskExecutionResult(False,now,'APSScheduler',None,index,None,None,True,job_id,'error',f'Schedule type not handled error: {self.scheduler.task_type}')

        next_run_at:dt.datetime =  job.next_run_time
        delta= (next_run_at.timestamp() +delay) - dt.datetime.now().timestamp()
        return TaskExecutionResult(True,now,'APSScheduler',naturaldelta(delta),index,str(self.scheduler._heaviness),None,False,job_id,'schedule','Task Added to the APSScheduler, delay or problem might occur')

    async def store_bkg_result(self,data,name,expiry,index=None):
        name=CeleryConstant.REDIS_BKG_TASK_ID_RESOLVER(name)
        if index==None:
            await self.redisService.hash_set(RedisConstant.CELERY_DB,name,mapping=data)
        else:
            await self.redisService.hash_set(RedisConstant.CELERY_DB,name,index,data)
        
        await self.redisService.expire(RedisConstant.CELERY_DB,name,expiry,nx=True)