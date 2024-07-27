from enum import Enum
from inspect import getmro
from typing import overload, get_overloads
from app.utils.constant import PARAMETER_KEY, RESOLVED_CLASS_KEY
from app.utils.helper import issubclass_of, is_abstract


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

    AbstractDependency: dict = {}

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
        pass


def InjectWCondition(baseClass: type, resolvedClass: function[type]):

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
        cls.AbstractDependency[baseClass] = {RESOLVED_CLASS_KEY: resolvedClass,
                                             PARAMETER_KEY: None}
        return cls

    return decorator