from enum import Enum
from inspect import getmro,isabstract
from typing import overload, get_overloads, Any
from utils.constant import RESOLVED_CLASS_KEY, RESOLVED_PARAMETER_KEY, RESOLVED_FUNC_KEY, RESOLVED_DEPS_KEY
from utils.helper import issubclass_of, is_abstract


AbstractDependency: dict[str, dict] = {}
AbstractModuleClasses: dict[str, type] = {}


class BuildErrorLevel(Enum):
    FAILURE = 4
    ABORT = 3
    WARNING = 2
    SKIP = 1


class BuildError(BaseException):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
    pass


class BuildFailureError(BuildError):
    pass


class BuildAbortError(BuildError):
    pass


class BuildWarningError(BuildError):
    pass


class BuildSkipError(BuildError):
    pass


class Module():

    def build(self):
        pass

    def kill(self):
        pass

    def log(self):
        pass

    def __repr__(self) -> str:
        return super().__repr__()
    
    # def __str__(self) -> str:
    #     return f"Module: {self.__class__.__name__} Hash: {self.__hash__()}"

    def _builder(self):
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

        except:
            pass

    def _killer(self):
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
        except:
            pass

def AbstractModuleClass(cls):
    AbstractModuleClasses[cls.__name__] = cls
    return cls

def InjectWCondition(baseClass: type, resolvedClass: Any): # NOTE we cannot create instance of the base class
    def decorator(cls: type):
        if is_abstract(cls,Module): AbstractModuleClasses[cls.__name__] = cls

        if not is_abstract(bClass=Module, cls=baseClass):
            pass
            # ABORT error
        if not issubclass_of(Module, baseClass):
            pass
            # ABORT error
        if not issubclass_of(Module, cls):
            pass
            # ABORT error
        AbstractDependency[cls.__name__] = {baseClass.__name__: {RESOLVED_FUNC_KEY: resolvedClass,
                                                                 RESOLVED_PARAMETER_KEY: None,
                                                                 RESOLVED_DEPS_KEY: None,
                                                                 RESOLVED_CLASS_KEY: None}}
        AbstractModuleClasses[baseClass.__name__] = baseClass
        
        return cls
    return decorator

