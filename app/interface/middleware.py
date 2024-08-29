

from definition._interface import Interface,IsInterface


@IsInterface
class InjectableMiddlewareInterface(Interface):

    def __init__(self) -> None:
        super().__init__()
        self.inject_middleware()


    def inject_middleware(self,):
        pass
    
    pass


@IsInterface
class EventInterface(Interface):

    def on_startup(self):
        pass

    def on_shutdown(self):
        pass