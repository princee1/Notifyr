from enum import Enum
from typing import Any, overload, Callable
from utils.constant import ConstantDependency
from utils.helper import issubclass_of


AbstractDependency: dict[str, dict] = {}
AbstractModuleClasses: dict[str, type] = {}
InjectAndBuildOnlyDependencies: dict = {}


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

    def destroy(self):
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

    def _destroyer(self):
        try:
            self.destroy()
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

def Fallback(cls):
    # VERIFY if the cls is really the resolved class
    # TODO get the abstract parent of the class
    return cls

def InjectWCondition(baseClass: type, resolvedClass: Any):
# NOTE we cannot create instance of the base class
    """
    The `InjectWCondition` decorator is used to specify a Dependency that will be resolved instead of its parent class. Thus
    we need to give to the decorator a function that will resolved base on other services value. At the injection moment the container 
    will run the function and resolve the class with the function given and inject to any class that has the decorator. 

    Another Parent class can use the decorator and specify for all the subclass by default. A subclass can specify for itself to. So
    the last one in the family class hierarchy will use the function to resolve its own dependency. Any (Module) class can decorate with multiple 
    decorator

    `example:: `

    class BaseS:
        pass

    class SA(BaseS):pass
    class SB(BaseS):pass
    class TestS:
        def build(self):
            self.counter = rnd.randint(0,5)
            pass

    def resolve(t: TestS):
        return SA if t.counter == 3 else SB

    @_module.InjectWCondition(BaseS, resolve)
    class A: pass
        def __init__(self, s:BaseS):
            self.s = s


    >>> CONTAINER.get(TestS,).counter
    >>> 3
    >>> CONTAINER.get(A).s.counter
    >>> 3
    """
    def decorator(cls: type):
        if not AbstractModuleClasses.__contains__(baseClass):
            pass
            # ABORT error
        if not issubclass_of(Module, baseClass):
            pass
            # ABORT error
        if not issubclass_of(Module, cls):
            pass
            # ABORT error
        AbstractDependency[cls.__name__] = {baseClass.__name__: {ConstantDependency.RESOLVED_FUNC_KEY: resolvedClass,
                                                                 ConstantDependency.RESOLVED_PARAMETER_KEY: None,
                                                                 ConstantDependency.RESOLVED_DEPS_KEY: None,
                                                                 ConstantDependency.RESOLVED_CLASS_KEY: None}}
        return cls
    return decorator

@overload
def InjectAndBuildOnly(builtCls: type, flag: bool):
    def decorator(cls: type):
        InjectAndBuildOnlyDependencies[cls.__name__] = {
            ConstantDependency.INJECT_ONLY_CLASS_KEY: builtCls,
            ConstantDependency.INJECT_ONLY_DEP_KEY: None,
            ConstantDependency.INJECT_ONLY_FLAG_KEY: flag,
            ConstantDependency.INJECT_ONLY_PARAMS_KEY: None,
            ConstantDependency.INJECT_ONLY_FUNC_KEY: None,
        }
        return cls
    return decorator

@overload
def InjectAndBuildOnly(builtCls: type, func: Callable):  
    def decorator(cls:type):
        InjectAndBuildOnlyDependencies[cls.__name__] = {
            ConstantDependency.INJECT_ONLY_CLASS_KEY: builtCls,
            ConstantDependency.INJECT_ONLY_DEP_KEY: None,
            ConstantDependency.INJECT_ONLY_FLAG_KEY: None,
            ConstantDependency.INJECT_ONLY_PARAMS_KEY: None,
            ConstantDependency.INJECT_ONLY_FUNC_KEY: func,
        }
        return
    return decorator
