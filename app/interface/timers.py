from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.calendarinterval import CalendarIntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.triggers.combining import AndTrigger
from typing import Callable, Any, Literal, TypedDict
import asyncio
from app.definition._error import BaseError
from app.definition._interface import Interface, IsInterface


class IntervalError(BaseError):
    ...

class IntervalParams(TypedDict):
    weeks: int = 0,
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    seconds: int = 0,
    start_date: Any | None = None,
    end_date: Any | None = None,
    timezone: Any | None = None,
    jitter: Any | None = None

class CronParams(TypedDict):
    year: str|int | Any | None = None,
    month: str|int | Any | None = None,
    day:  str|int | Any | None = None,
    week:  str|int | Any | None = None,
    day_of_week: str|int | Any | None = None,
    hour: str|int | Any | None = None,
    minute: str|int | Any | None = None,
    second: str|int | Any | None = None,
    start_date: Any | None = None,
    end_date: Any | None = None,
    timezone: Any | None = None,
    jitter: Any | None = None

class DateParams(TypedDict):
    run_date: Any | None = None
    timezone: Any | None = None

@IsInterface
class SchedulerInterface(Interface):
    def __init__(self,misfire_grace_time:float|None=None,jobstores:dict = lambda: {'default':MemoryJobStore()},
                jobstore='default',executors = lambda v:{"asyncio-executor": AsyncIOExecutor(),'asyncio':{'type':'asyncio'},'thread':ThreadPoolExecutor(v) }
                ,executor:Literal['asyncio','asyncio-executor','thread']='thread',replace_existing=False,coalesce:bool = True,thread_pool_count:int=20):
        self.jobstores= jobstores if isinstance(jobstores,dict) else jobstores()
        self.executors= executors if isinstance(executors,dict) else executors(thread_pool_count)
        self.executor = executor
        self.jobstore = jobstore
        self.misfire_grace_time = misfire_grace_time
        self.replace_existing = replace_existing
        self.coalesce = coalesce
        self._scheduler = AsyncIOScheduler(jobstores=self.jobstores,executors=self.executors)
        
    def now_schedule(self,delay:float,action: Callable[..., Any],args,kwargs,id=None,name=None,jobstore=None,executor=None):
        if not isinstance(delay,(int,float)):
            delay = random.random() *10
        trigger = DateTrigger(datetime.now()+timedelta(seconds=delay))
        return self._schedule(action,args,kwargs,trigger,jobstore=jobstore,id=id,name=name,executor = executor)

    def interval_schedule(self,delay: IntervalParams|IntervalTrigger,action: Callable[..., Any],args,kwargs,id=None,name=None,jobstore=None,executor=None):
        """Schedule a task with a delay. Supports async and sync functions."""
        if isinstance(delay,IntervalTrigger):
            trigger = delay
        else:
            trigger = IntervalTrigger(**delay)
        self._schedule(action, args, kwargs, trigger,id,name,jobstore,executor)

    def cron_schedule(self,cron: CronParams|CronTrigger,action: Callable[..., Any],args,kwargs,id=None,name=None,jobstore=None,executor=None):
        if isinstance(cron,CronTrigger):
            trigger=cron
        else:
            trigger = CronTrigger(**cron)
        return self._schedule(action, args, kwargs, trigger,id,name,jobstore,executor)

    def date_schedule(self,date:datetime,action: Callable[..., Any],args,kwargs,id=None,name=None,jobstore=None,executor=None):
        trigger = DateTrigger(date)
        return self._schedule(action, args, kwargs, trigger,id,name,jobstore,executor)
    
    def _schedule(self, action, args, kwargs, trigger,id=None,name=None,jobstore=None,executor=None,run_date=None):
        
        jobstore,executor = self.update_verify_store(jobstore,executor,True)

        if asyncio.iscoroutinefunction(action):
            return self._scheduler.add_job(action, trigger, args=args, id = id,kwargs=kwargs,misfire_grace_time=self.misfire_grace_time,jobstore=jobstore,coalesce=self.coalesce,executor=self.executor)
        else:
            return self._scheduler.add_job(self._run_sync, trigger, args=(action, *args),id = id, name=name,kwargs=kwargs,misfire_grace_time=self.misfire_grace_time,jobstore=jobstore,coalesce=self.coalesce)

    def start(self):
        if self._scheduler.running:
            return
        self._scheduler.start()

    async def _run_sync(self, func: Callable[..., Any], *args, **kwargs):
        """Run a synchronous function asynchronously."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, func, *args, **kwargs)

    def shutdown(self,wait=True):
        """Shut down the scheduler."""
        if not self._scheduler.running:
            return
        self._scheduler.shutdown(wait)
    
    def pause(self,job_id):
        self._scheduler.pause_job(job_id)
    
    def resume(self,job_id):
        self._scheduler.resume_job(job_id)

    def update_verify_store(self,jobstore:str=None,executor:str=None,verify_only=False):
        if jobstore:
            if jobstore not in self.jobstores:
                raise ValueError('Jobstore not valid')
            if not verify_only:
                self.jobstore = jobstore
        else:
            jobstore = self.jobstore
        if executor:
            if executor not in self.executor:
                raise ValueError('Jobstore not valid')
            if not verify_only:
                self.executor = executor
        else:
            executor =  self.executor
        
        return jobstore,executor

@IsInterface
class IntervalInterface(Interface):
    def __init__(self,start_now:bool=False,interval:float=None):
        self._task = None
        self._interval = interval
        self.start_now = start_now
        self.active = True

    async def _run_interval(self):
        """Internal method to repeatedly call the callback at specified intervals."""
        if not self.start_now:
            while self.active:
                await asyncio.sleep(self._interval)
                await self._run_callback()
        else:
            while self.active:
                await self._run_callback()
                await asyncio.sleep(self._interval)

    def start_interval(self, interval: float=None,start_now:bool=None) -> None:
        """Start a new interval timer."""
        self.stop_interval()  # Stop any running interval
        
        self.active = True
        if interval!=None:
            self._interval = interval
        
        if start_now!=None and isinstance(start_now,bool):
            self.start_now = start_now
        
        if self._interval == None or not isinstance(self._interval,(int,float)) or self._interval <0:
            raise IntervalError(self._interval)
        self._task = asyncio.create_task(self._run_interval())

    def stop_interval(self) -> None:
        """Stop the interval timer."""
        if self._task is not None:
            self._task.cancel()
            self._task = None
            #self._interval = None
        self.active = False

    def is_running(self) -> bool:
        """Check if the interval timer is running."""
        return self._task is not None and not self._task.done()

    def callback(self):
        ...
    
    async def _run_callback(self):
        if asyncio.iscoroutinefunction(self.callback):
            await self.callback()
        else:
            self.callback()
