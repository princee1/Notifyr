from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import Callable, Any
import asyncio
from app.definition._interface import Interface, IsInterface
from abc import abstractmethod

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
    def __init__(self,):
        self._task = None
        self._interval = None

    async def _run_interval(self):
        """Internal method to repeatedly call the callback at specified intervals."""
        while True:
            await asyncio.sleep(self._interval)
            self.callback()

    def start_interval(self, interval: float) -> None:
        """Start a new interval timer."""
        self.stop_interval()  # Stop any running interval
        self._interval = interval
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
