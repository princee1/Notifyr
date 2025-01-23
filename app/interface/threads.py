from threading import Event, Thread
from typing import overload
from app.definition._interface import Interface, IsInterface


@IsInterface
class ThreadInterface(Interface):
    def __init__(self) -> None:
        super().__init__()
        self.thread = Thread(target=self._target, name=self.name)

    def _target(self) -> None:
        self._run()
        pass

    def start(self):
        self.thread.start()

    def join(self):
        self.thread.join()

    def _run(self):
        pass

    @property
    def name(self):
        return None


@IsInterface
class InfiniteThreadInterface(ThreadInterface):

    def __init__(self) -> None:
        super().__init__()
        self.event = Event()
        self.active = True
        self.base_waitTime = None
        self.waitTime =self.base_waitTime
        self.paused = False

    def kill(self):
        """
        The function sets the event  to true, which causes the thread to exit the while loop and end
        the thread
        """
        self.active = False
        self.event.set()

    def _todo(self):
        pass

    def _run(self):
        while self.active:
            print('running...')
            try:
                self.event.wait(self.waitTime)
                self.reset()
                if self.active:
                    self._todo()
                self.event.clear()
            except:
                pass
        

    @overload
    def pause(self):
        self.paused = True
        self.waitTime = self.base_waitTime

    def reset(self):
        self.paused = False
        self.waitTime = self.base_waitTime

    @overload
    def pause(self, time):
        self.paused = True
        self.waitTime = time

    def play(self):
        self.event.set()
    
    def join(self):
        self.active = False
        return super().join()


@IsInterface
class ControlledThreadInterface(InfiniteThreadInterface):
    def changeState(self):
        pass
    pass


@IsInterface
class TaskThreadInterface(ThreadInterface):

    def _join(self):
        pass

    def join(self):
        self.thread.join()
        return self._join()
