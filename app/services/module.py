from enum import Enum

class BuildErrorLevel(Enum):
    
    pass


class BuildError(BaseException):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
    pass

class Module():

    def build(self):
        pass

    def kill(self):
        pass

    def __builder(self):
        try:
            self.build()
            pass
        except:
            pass
        pass

    def __killer(self):
        try:
            self.kill()
            pass
        except:
            pass
        pass

    pass