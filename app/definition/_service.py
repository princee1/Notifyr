from enum import Enum
from typing import Any, overload, Callable
from utils.prettyprint import PrettyPrinter
from utils.constant import DependencyConstant
from utils.helper import issubclass_of
import warnings


AbstractDependency: dict[str, dict] = {}
AbstractServiceClasses: dict[str, type] = {}
BuildOnlyIfDependencies: dict = {}
PossibleDependencies: dict[str, list[type]] = {}


class BuildErrorLevel(Enum):
    ABORT = 4
    FAILURE = 3
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


class BuildFallbackError(BuildError):
    pass


class Service():

    def __init__(self) -> None:
        self.__builded: bool = False
        self.__destroyed: bool = False
        self.prettyPrinter = PrettyPrinter()

    def build(self):
        warnings.warn(f"This method from the service class {self.__class__.__name__} has not been implemented yet.", UserWarning,2)
        pass

    def destroy(self):
        warnings.warn(f"This method from the service class {self.__class__.__name__} has not been implemented yet.", UserWarning,2)
        pass

    def log(self):
        pass

    def __repr__(self) -> str:
        return super().__repr__()

    def __str__(self) -> str:
        return f"Service: {self.__class__.__name__} Hash: {self.__hash__()}"

    def _builder(self):
        try:
            self.build()
            self.__builded = True
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
            self.__destroyed = True
            self.__builded = False
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


def AbstractServiceClass(cls):
    AbstractServiceClasses[cls.__name__] = cls
    return cls


@overload
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
        if not AbstractServiceClasses.__contains__(baseClass):
            pass
            # TODO ABORT error
        if not issubclass_of(Service, baseClass):
            pass
            # TODO ABORT error
        if not issubclass_of(Service, cls):
            pass
            # TODO  ABORT error
        AbstractDependency[cls.__name__] = {baseClass.__name__: {DependencyConstant.RESOLVED_FUNC_KEY: resolvedClass,
                                                                 DependencyConstant.RESOLVED_PARAMETER_KEY: None,
                                                                 DependencyConstant.RESOLVED_DEPS_KEY: None,
                                                                 DependencyConstant.RESOLVED_CLASS_KEY: None}}
        return cls
    return decorator


@overload
def InjectWCondition(baseClass: type, resolvedClass: Any,
                     fallback: list[type]): pass


@overload
def InjectWCondition(baseClass: type, fallback: list[type]): pass


@overload
def BuildOnlyIf(flag: bool):
    def decorator(cls: type):
        BuildOnlyIfDependencies[cls.__name__] = {
            DependencyConstant.BUILD_ONLY_CLASS_KEY: cls,
            DependencyConstant.BUILD_ONLY_DEP_KEY: None,
            DependencyConstant.BUILD_ONLY_FLAG_KEY: flag,
            DependencyConstant.BUILD_ONLY_PARAMS_KEY: None,
            DependencyConstant.BUILD_ONLY_FUNC_KEY: None,
        }
        return cls
    return decorator


@overload
def BuildOnlyIf(func: Callable[..., bool]):
    """ WARNING The builtCls must be in the Dependency list if you want to call this decorator, 
        since the container cant add it while load all the dependencies,
        if dont want the built class to call the builder function simply remove from the dependency list
    """
    def decorator(cls: type):
        BuildOnlyIfDependencies[cls.__name__] = {
            DependencyConstant.BUILD_ONLY_CLASS_KEY: cls,
            DependencyConstant.BUILD_ONLY_DEP_KEY: None,
            DependencyConstant.BUILD_ONLY_FLAG_KEY: None,
            DependencyConstant.BUILD_ONLY_PARAMS_KEY: None,
            DependencyConstant.BUILD_ONLY_FUNC_KEY: func,
        }
        return
    return decorator


def SkipBuild(cls):
    decorator = BuildOnlyIf(cls)
    return decorator(False)


def PossibleDep(dependencies: list[type]):
    def decorator(cls: type):
        PossibleDependencies[cls.__name__] = [d.__name__ for d in dependencies]
        return cls
    return decorator
