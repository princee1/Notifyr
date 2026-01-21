
from enum import Enum
from typing import TypedDict


class BuildReport(TypedDict):
    ...

class BuildErrorLevel(Enum):
    ABORT = 4
    FAILURE = 3
    WARNING = 2
    SKIP = 1
#################################            #####################################


class BuildError(BaseException):
    def __init__(self,*args: object) -> None:
        super().__init__(*args)
    pass


class BuildFailureError(BuildError):
    pass


class BuildAbortError(BuildError):
    pass


class BuildWarningError(BuildError):
    pass

class BuildOkError(BuildError):
    pass

class BuildSkipError(BuildError):
    pass


class BuildFallbackError(BuildError):
    pass


class BuildNotImplementedError(BuildError):
    ...


#################################            #####################################

class NotBuildedError(BuildError):
    ...

class DestroyedError(BuildError):
    ...

#################################            #####################################

class ServiceNotAvailableError(BuildError):
    pass

class ServiceMajorSystemFailureError(BufferError):
    pass
class ServiceTemporaryNotAvailableError(BuildError):
    
    def __init__(self, *args,service=None):
        super().__init__(*args)
        self.service = service
        

class MethodServiceNotAvailableError(BuildError):
    pass

class MethodServiceNotExistsError(BuildError):
    ...

class MethodServiceNotImplementedError(BuildError):
    ...

class ServiceNotImplementedError(BuildError):
    ...

class ServiceChangingStateError(BuildError):
    ...

class ServiceDoesNotExistError(BuildError):
    ...

class StateProtocolMalFormattedError(BuildError):
    ...

#################################            #####################################

class MiniServiceAlreadyExistsError(BuildError):
    ...

class MiniServiceDoesNotExistsError(BuildError):
    
    def __init__(self, miniService_id:str):
        super().__init__()
        self.miniService_id = miniService_id

    @property    
    def message(self):
        return f"MiniService with id '{self.miniService_id}' does not exist."

class MiniServiceCannotBeIdentifiedError(BuildError):
    ...

class MiniServiceStrictValueNotValidError(BuildError):
    ...