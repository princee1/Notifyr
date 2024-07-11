
import injector

class Container():

    def __init__(self) -> None:
        self.app = injector.Injector()
    pass

    def bind(self,type):
        pass
    
    def get(self):
        pass



CONTAINER: Container = Container()

