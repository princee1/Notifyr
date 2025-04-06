import sched
import time
import asyncio
from app.definition._interface import Interface, IsInterface
from abc import abstractmethod


@IsInterface
class SchedulerInterface(Interface):
    def __init__(self):
        self._scheduler = sched.scheduler(time.time, time.sleep)

    def schedule(self, delay: float, priority: int, action, argument=(), kwargs={}) -> sched.Event:
        """Schedule a task with a delay and priority. Supports async functions."""
        if asyncio.iscoroutinefunction(action):
            async def async_wrapper():
                await action(*argument, **kwargs)
            action = lambda: asyncio.run(async_wrapper())
        elif asyncio.iscoroutine(action):
            async def async_wrapper():
                await action
            action = lambda: asyncio.run(async_wrapper())
        else:
            ...
        event = self._scheduler.enter(delay, priority, action, argument, kwargs)
        return event

    async def run(self) -> None:
        """Run the scheduled tasks asynchronously."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._scheduler.run)

    def __cancel(self, event: sched.Event) -> None:
        """Cancel a scheduled task."""
        try:
            self._scheduler.cancel(event)
        except ValueError:
            pass  # Event may have already been executed or canceled

    def _is_empty(self) -> bool:
        """Check if the scheduler has any pending tasks."""
        return not self._scheduler.queue

    def clear(self) -> None:
        """Cancel all scheduled tasks."""
        for event in list(self._scheduler.queue):
            self.__cancel(event)


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
