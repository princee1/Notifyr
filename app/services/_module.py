from enum import Enum
from inspect import getmro
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


def InjectWCondition(baseClass: type, resolvedClass: Any):
    def decorator(cls: Module):
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
        return cls
    return decorator


def AbstractModuleClass():
    def decorator(cls: type):
        AbstractModuleClasses[cls.__name__] = cls
        return cls

    return decorator
