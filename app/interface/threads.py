import asyncio
from typing import overload
from app.definition._interface import Interface, IsInterface

@IsInterface
class AsyncInterface(Interface):
    def __init__(self) -> None:
        super().__init__()
        self.task = None  # Will hold an asyncio task

    async def _target(self):
        await self._run()

    def start(self):
        """Starts the async task"""
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._target())

    async def stop(self):
        """Stops the async task gracefully"""
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def _run(self):
        pass

    @property
    def name(self):
        return None


@IsInterface
class InfiniteAsyncInterface(AsyncInterface):
    def __init__(self) -> None:
        super().__init__()
        self.event = asyncio.Event()
        self.active = True
        self.base_waitTime = None
        self.waitTime = self.base_waitTime
        self.paused = False

    def kill(self):
        """Stops execution and ends the async task"""
        self.active = False
        self.event.set()

    async def _todo(self):
        pass

    async def _run(self):
        """Runs the infinite loop asynchronously"""
        while self.active:
            try:
                await asyncio.sleep(self.waitTime or 0)  # Sleep for waitTime duration
                self.event.wait()
                self.reset()
                if self.active:
                    await self._todo()
                self.event.clear()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in _run: {e}")

    @overload
    def pause(self):
        """Pauses execution"""
        self.paused = True
        self.waitTime = self.base_waitTime

    def reset(self):
        """Resets the pause state"""
        self.paused = False
        self.waitTime = self.base_waitTime

    @overload
    def pause(self, time):
        """Pauses execution for a specific time"""
        self.paused = True
        self.waitTime = time

    def play(self):
        """Resumes execution"""
        self.event.set()

    async def stop(self):
        """Stops the async task and terminates execution"""
        self.active = False
        await super().stop()


@IsInterface
class ControlledAsyncInterface(InfiniteAsyncInterface):
    async def changeState(self):
        pass


@IsInterface
class TaskAsyncInterface(AsyncInterface):
    async def _join(self):
        pass

    async def stop(self):
        """Stops execution and calls _join()"""
        await super().stop()
        await self._join()
