import asyncio
from dataclasses import asdict
from typing import Any, Coroutine, Literal, ParamSpec, TypedDict
from fastapi import Depends
from humanize import naturaldelta
from app.classes.celery import UNSUPPORTED_TASKS, AlgorithmType, Compute_Weight, SchedulerModel, TaskExecutionResult, TaskRetryError, TaskType, add_warning_messages, s
from app.classes.env_selector import EnvSelection, StrategyType, get_selector
from app.depends.dependencies import get_request_id
from starlette.background import BackgroundTask,BackgroundTasks
from app.depends.variables import *
import datetime as dt
from app.container import Get
from app.services.celery_service import CeleryService
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.monitoring_service import MonitoringService
from app.services.task_service import TaskService

P = ParamSpec("P")

class TaskConfig(TypedDict):
    task: BackgroundTask | Coroutine
    delay: float

class TaskMeta(TypedDict):
    request_id:str
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
    
    _schedule_env_selection:list[EnvSelection] = ['aps','worker']
    _not_allowed_aps_task_type = set[TaskType] = {TaskType.RRULE,TaskType.SOLAR}

    def __init__(self,backgroundTasks:BackgroundTasks,response:Response,request:Request,request_id: str = Depends(get_request_id), background: bool = Depends(background_query), runtype: RunType = Depends(runtype_query), ttl=Query(1, ge=0, le=24*60*60), save_results:bool=Depends(save_results_query), return_results:bool=Depends(get_task_results),retry:bool=Depends(retry_query),split:bool = Depends(split_query),algorithm:AlgorithmType = Depends(algorithm_query),strategy:StrategyType = Depends(strategy_query)):
        self.return_results:bool = return_results
        self.backgroundTasks = backgroundTasks
        self.response = response
        self.request = request

        self.taskConfig: list[TaskConfig] = []
        self.weight = 0.0
        self.scheduler: SchedulerModel = None
        self.task_result:list[TaskExecutionResult] = []
        self.meta: TaskMeta = TaskMeta(request_id=request_id,background=background,runtype=runtype,save_result=save_results,ttl=ttl,tt=0,ttd=0,retry=retry,split=split,algorithm=algorithm,strategy=strategy)

        self.celeryService = Get(CeleryService)
        self.configService = Get(ConfigService)
        self.taskService = Get(TaskService)
        self.redisService = Get(RedisService)
        self.monitoringService = Get(MonitoringService)

        self.register_backgroundTask()

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
    
    async def select_task_env(self,task_weight:float,needed_envs:list[EnvSelection]=None)->EnvSelection:
        async with self.celeryService.statusLock.reader:
            p1 = await len(self.celeryService._workers)

        if p1 < 0:
            p1 = 0

        workers_count = self.configService.CELERY_WORKERS_COUNT

        p2  = p1 / workers_count if workers_count > 0 else 0
        p3 = task_weight

        return get_selector(self.meta['strategy']).select(p1, p2, p3)

    def register_backgroundTask(self):
        async def callback():
            await asyncio.sleep(0.1)
            if len(self.taskConfig)==0: 
                return
            return await self._run_task_in_background()
        self.backgroundTasks.add_task(callback)

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
            'message': self.scheduler._message if self.scheduler else {},
        }

    @property
    def schedule_ttd(self):
        return self.meta['ttd'] - self.taskConfig[0]['delay']
        
    async def _run_task_in_background(self):
        task_len = len(self.taskConfig)
        ttl=self.meta['ttl']
        is_saving_result = self.meta['save_result']
        runType = self.meta['runtype']
        is_retry = self.meta['retry']

        for i, t in enumerate(self.taskConfig):  # TODO add the index i to the results
            task:BackgroundTask = t['task']
            delay = t['delay']
            if delay and delay>0:
                await asyncio.sleep(delay)

            data=None if runType == 'parallel' else []
            self.monitoringService.background_task_count.inc()
           
            async def callback():

                async def parse_error(e:Exception,bypass=False):
                    result = {'error_class':e.__class__,'args':str(e.args)}
                    if bypass:
                        result['bypass']=True
                    if is_saving_result:
                        if runType == 'sequential':
                            data.append(result)
                        else:
                            await self.redisService.store_bkg_result(result, self.meta['request_id'],ttl)
                    
                    if runType =='parallel':
                        self.monitoringService.background_task_count.dec()
                        
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
                            await self.redisService.store_bkg_result(result,self.meta['request_id'],ttl)
                    
                    if runType=='parallel':
                        self.monitoringService.background_task_count.dec()                
                    return result
                except TaskRetryError as e:
                    error = e.error
                    if is_retry:
                        if not isinstance(self.scheduler,s) and isinstance(task,BackgroundTask):
                            self.celeryService.trigger_task_from_scheduler(self.scheduler,i,*task.args,**task.kwargs)
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
            await self.redisService.store_bkg_result(data, self.meta['request_id'],ttl)
            self.monitoringService.background_task_count.dec(task_len)
       
    async def _offload_task(self,weight: float,delay: float,index:int,callback: Callable, *args, **kwargs)->TaskExecutionResult:

        algorithm = self.meta['algorithm']

        if algorithm == 'route' and isinstance(self.scheduler, SchedulerModel) and self.scheduler.task_type != TaskType.NOW:
            algorithm = 'worker'
            add_warning_messages(UNSUPPORTED_TASKS, self.scheduler, index=index)

        match algorithm:
            case  'normal':
                return await self._normal_offload(weight,delay,index,callback, *args, **kwargs)
            case 'worker':
                return self.celeryService.trigger_task_from_scheduler(self.scheduler,index,weight,*args, **kwargs)
            case 'route':
                return await self._route_offload(None,weight,delay,index,callback, *args, **kwargs)
            case 'mix':
                return await self._mix_offload(weight,delay,index,callback, *args, **kwargs)
            case 'aps':
                return self._schedule_aps_task(weight,delay,index,callback,*args,**kwargs)
            case _:
                now = dt.datetime.now().isoformat()
                return TaskExecutionResult(False,now,'RouteHandler',None,index,None,None,True,self.meta['task_id'],None,message=f'Algorithm not supported {algorithm}')

    async def _normal_offload(self,weight:float, delay: float,index:int, callback: Callable, *args, **kwargs)->TaskExecutionResult:
        if self.scheduler.task_type == TaskType.NOW:
            return await self._route_offload(None,weight,delay,index,callback,*args,**kwargs)
        elif ...:
            return  self.celeryService.trigger_task_from_scheduler(self.scheduler,index,weight, *args, **kwargs)
        elif self.scheduler.task_type in self._not_allowed_aps_task_type:
            now = dt.datetime.now().isoformat()
            return TaskExecutionResult(False,now,'APSScheduler',None,index,None,None,True,self.meta['request_id'],None,f'TaskType not supported by APSScheduler: {self.scheduler.task_type}')
        else:
            return self._schedule_aps_task(weight,delay,index,callback,*args,**kwargs)

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
                        self.celeryService.trigger_task_from_scheduler(self.scheduler,index,weight,*args, **kwargs)
                return TaskExecutionResult(handler='Route Handler',offloaded=True,date=now,index=index,error=True,result=None,heaviness=str(self.scheduler._heaviness))

    async def _mix_offload(self,weight:float,delay,index:int, callback: Callable, *args, **kwargs)->TaskExecutionResult:
        match self.scheduler.task_type:
            case TaskType.NOW:
                env = await self.select_task_env(weight,None)
                if env.startswith('route'):
                    return await self._route_offload(env,weight,delay,index,callback,*args,**kwargs)
                elif env == 'worker':
                    return self.celeryService.trigger_task_from_scheduler(self.scheduler,index,weight, *args, **kwargs)
                else:
                    return self._schedule_aps_task(weight,delay,index,callback,*args,**kwargs)
            case (TaskType.DATETIME,TaskType.TIMEDELTA,TaskType.INTERVAL,TaskType.CRONTAB):
                if (await self.select_task_env(weight,self._schedule_env_selection)) == 'worker':
                    return self.celeryService.trigger_task_from_scheduler(self.scheduler,index,weight, *args, **kwargs)
                else:
                    return self._schedule_aps_task(weight,delay,index,callback,*args,**kwargs)
            case (TaskType.SOLAR,TaskType.RRULE):
                return self.celeryService.trigger_task_from_scheduler(self.scheduler,index,weight, *args, **kwargs)
            case _:
                now = dt.datetime.now().isoformat()
                return TaskExecutionResult(False,now,'RouteHandler',None,index,None,error=True,task_id=self.meta['request_id'],type=None,message=f'TaskType not supported by the server: {self.scheduler.task_type}')

    def _schedule_aps_task(self,weight,delay,index:int,callback:Callable,*args,**kwargs):
        now = dt.datetime.now().isoformat()
        match self.scheduler.task_type:
            case TaskType.NOW:
                job = self.taskService.now_schedule(delay,callback,args,kwargs,self.meta['request_id'])
            case (TaskType.DATETIME,TaskType.TIMEDELTA):
                job = self.taskService.date_schedule(self.scheduler._schedule._aps_object,callback,args,kwargs,self.meta['request_id'])
            case TaskType.CRONTAB:
                job = self.taskService.cron_schedule(self.scheduler._schedule._aps_object,callback,args,kwargs,self.meta['request_id'])
            case TaskType.INTERVAL:
                job = self.taskService.interval_schedule(self.scheduler._schedule._aps_object,callback,args,kwargs,self.meta['request_id'])
            case _:
                return TaskExecutionResult(False,now,'APSScheduler',None,index,None,None,True,self.meta['request_id'],'error',f'Schedule type not handled error: {self.scheduler.task_type}')

        return TaskExecutionResult(True,now,'APSScheduler',None,index,str(self.scheduler._heaviness),None,False,self.meta['request_id'],'schedule','Task Added to the APSScheduler, delay or problem might occur')
