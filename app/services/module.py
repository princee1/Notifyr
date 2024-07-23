from enum import Enum

class BuildErrorLevel(Enum):
    FAILURE = 4
    ABORT = 3
    WARNING = 2
    SKIP = 1


class BuildError(BaseException):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
    pass


class BuildFailureError(BuildError): pass

class BuildAbortError(BuildError): pass

class BuildWarningError(BuildError): pass

class BuildSkipError(BuildError): pass


class Module():

    def build(self):
        pass

    def kill(self):
        pass

    def log(self):
        pass

    def __builder(self):
        try:
            self.build()
        except BuildFailureError as e:
            pass

        except BuildAbortError as e:
            pass

        except BuildWarningError as e:
            pass

        except BuildSkipError as e:
            pass

    def __killer(self):
        try:
            self.kill()
            pass
        except BuildFailureError as e:
            pass

        except BuildAbortError as e:
            pass

        except BuildWarningError as e:
            pass

        except BuildSkipError as e:
            pass
        pass

    pass