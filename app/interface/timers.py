from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import Callable, Any
import asyncio
from app.definition._error import BaseError
from app.definition._interface import Interface, IsInterface
from abc import abstractmethod


class IntervalError(BaseError):
    ...

@IsInterface
class SchedulerInterface(Interface):
    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        
    def schedule(
        self,
        delay: float,
        action: Callable[..., Any],
        *args,
        **kwargs
    ):
        """Schedule a task with a delay. Supports async and sync functions."""
        trigger = IntervalTrigger(seconds=delay)
        if asyncio.iscoroutinefunction(action):
            self._scheduler.add_job(action, trigger, args=args, kwargs=kwargs)
        else:
            self._scheduler.add_job(self._run_sync, trigger, args=(action, *args), kwargs=kwargs)

    def start(self):
        self._scheduler.start()

    async def _run_sync(self, func: Callable[..., Any], *args, **kwargs):
        """Run a synchronous function asynchronously."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, func, *args, **kwargs)

    def shutdown(self):
        """Shut down the scheduler."""
        self._scheduler.shutdown()


@IsInterface
class IntervalInterface(Interface):
    def __init__(self,start_now:bool=False,interval:float=None):
        self._task = None
        self._interval = interval
        self.start_now = start_now

    async def _run_interval(self):
        """Internal method to repeatedly call the callback at specified intervals."""
        if not self.start_now:
            while True:
                await asyncio.sleep(self._interval)
                self.callback()
        else:
            while True:
                self.callback()
                await asyncio.sleep(self._interval)

    def start_interval(self, interval: float=None,start_now:bool=None) -> None:
        """Start a new interval timer."""
        self.stop_interval()  # Stop any running interval
        
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
            self._interval = None

    def is_running(self) -> bool:
        """Check if the interval timer is running."""
        return self._task is not None and not self._task.done()

    def callback(self):
        ...
