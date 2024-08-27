from threading import Event, Thread
from typing import overload
from definition._interface import Interface, IsInterface


@IsInterface
class ThreadInterface(Interface):
    def __init__(self) -> None:
        super().__init__()
        self.thread = Thread(target=self._target, name=self.name)
        self.thread.start()

    def _target(self) -> None:
        self._run()
        pass

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
        self.waitTime = None
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
        """
        It waits for a timeout period, then checks if there are any notifications to be shown, and if there
        are, it shows them.
        """
        while self.active:
            try:
                self.event.wait(self.waitTime)
                if self.active:
                    self._todo()
                self.event.clear()
            except:
                pass

    @overload
    def pause(self):
        pass

    @overload
    def pause(self, time):
        pass

    def play(self):
        pass

    pass


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
