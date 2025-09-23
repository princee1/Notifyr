from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.calendarinterval import CalendarIntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.combining import AndTrigger
from typing import Callable, Any, TypedDict
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
    def __init__(self,misfire_grace_time:float|None=None):
        self._scheduler = AsyncIOScheduler()
        self.misfire_grace_time = misfire_grace_time
        
    def interval_schedule(
        self,
        delay: IntervalParams,
        action: Callable[..., Any],
        *args,
        **kwargs
    ):
        """Schedule a task with a delay. Supports async and sync functions."""
        trigger = IntervalTrigger(**delay)
        self._schedule(action, args, kwargs, trigger)

    def cron_schedule(
        self,
        cron: CronParams,
        action: Callable[..., Any],
        *args,
        **kwargs
    ):

        trigger = CronTrigger(**cron)
        self._schedule(action, args, kwargs, trigger)

    def date_schedule(
        self,
        date: DateParams,
        action: Callable[..., Any],
        *args,
        **kwargs
    ):
        trigger = DateTrigger(**date)
        self._schedule(action, args, kwargs, trigger)

    def _schedule(self, action, args, kwargs, trigger,id=None,name=None):
        if asyncio.iscoroutinefunction(action):
            self._scheduler.add_job(action, trigger, args=args, id = id,kwargs=kwargs,misfire_grace_time=self.misfire_grace_time)
        else:
            self._scheduler.add_job(self._run_sync, trigger, args=(action, *args),id = id, name=name,kwargs=kwargs,misfire_grace_time=self.misfire_grace_time)

    def start(self):
        self._scheduler.start()

    async def _run_sync(self, func: Callable[..., Any], *args, **kwargs):
        """Run a synchronous function asynchronously."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, func, *args, **kwargs)

    def shutdown(self):
        """Shut down the scheduler."""
        self._scheduler.shutdown()
    
    def pause(self,job_id):
        self._scheduler.pause_job(job_id)
    
    def resume(self,job_id):
        self._scheduler.resume_job(job_id)


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
