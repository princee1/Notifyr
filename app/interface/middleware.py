

from definition._interface import Interface


class InjectableMiddlewareInterface(Interface):

    def __init__(self) -> None:
        super().__init__()
        self.inject_middleware()


    def inject_middleware(self,):
        pass
    
    pass
