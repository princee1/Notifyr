from enum import Enum
from typing import Any, overload, Callable, Type, TypeVar, Dict
from utils.prettyprint import PrettyPrinter, PrettyPrinter_
from utils.constant import DependencyConstant
from utils.helper import issubclass_of
import warnings
import datetime as dt


AbstractDependency: Dict[str, dict] = {}
AbstractServiceClasses: Dict[str, type] = {}
BuildOnlyIfDependencies: Dict = {}
PossibleDependencies: Dict[str, list[type]] = {}
OptionalDependencies: Dict[str, list[type]] = {}
__DEPENDENCY: list[type] = []


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


class ServiceNotAvailableError(BuildError):
    pass

class MethodServiceNotAvailableError(BuildError):
    pass



class Service():

    def __init__(self) -> None:
        self._status:BuildErrorLevel = None
        self._builded: bool = False
        self._destroyed: bool = False
        self.prettyPrinter: PrettyPrinter = PrettyPrinter_

    def build(self):
        # warnings.warn(
        #     f"This method from the service class {self.__class__.__name__} has not been implemented yet.", UserWarning, 2)
        pass

    def destroy(self):
        warnings.warn(
            f"This method from the service class {self.__class__.__name__} has not been implemented yet.", UserWarning, 2)
        pass

    def log(self):
        pass

    def __repr__(self) -> str:
        return super().__repr__()

    def __str__(self) -> str:
        return f"Service: {self.__class__.__name__} Hash: {self.__hash__()}"

    def buildReport(self):
        pass

    def destroyReport(self):
        pass

    def _builder(self):
        try:
            now = dt.datetime.now()
            #self.prettyPrinter.show()
            #self.prettyPrinter.info(f'[{now}] Current Building the service: {self.__class__.__name__}',saveable=False)
            self.build()
            self._builded = True
            self._destroyed = False
            self.prettyPrinter.success(f'[{now}] Successfully built the service: {self.__class__.__name__}',saveable=True)
            self.prettyPrinter.wait(0.1,False)

        except BuildFailureError as e:
            self.prettyPrinter.error(f'[{now}] Error while building the service: {self.__class__.__name__}',saveable=True)
            pass

        except BuildAbortError as e:
            self.prettyPrinter.error(f'[{now}] Error while building the service: {self.__class__.__name__}',saveable=True)
            pass

        except BuildWarningError as e:
            self.prettyPrinter.warning(f'[{now}] Problem encountered while building the service: {self.__class__.__name__}',saveable=True)

            pass

        except BuildSkipError as e:
            self.prettyPrinter.message(f'[{now}] Problem encountered while building the service : {self.__class__.__name__} Skipping for now NOTE: this can cause some error',saveable=True)
            pass
        

        finally:
            self.buildReport()

    def _destroyer(self):
        try:
            self.destroy()
            self._destroyed = True
            self._builded = False
            pass
        
        except BuildFailureError as e:
            pass

        except BuildAbortError as e:
            pass

        except BuildWarningError as e:
            pass

        except BuildSkipError as e:
            pass

        finally:
            self.destroyReport()


S = TypeVar('S', bound=Service)


def AbstractServiceClass(cls: S) -> S:
    if cls in __DEPENDENCY:
        __DEPENDENCY.remove(cls)
    AbstractServiceClasses[cls.__name__] = cls

    return cls


def ServiceClass(cls: S) -> S:
    if cls.__name__ not in AbstractServiceClasses and cls not in __DEPENDENCY:
        __DEPENDENCY.append(cls)
    return cls


@overload
def InjectWithCondition(baseClass: type, resolvedClass: type[Service]):
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
    def decorator(cls: Type[S]) -> Type[S]:
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
def InjectWithCondition(baseClass: type[Service], resolvedClass: Callable[..., type[Service]],
                        fallback: list[type[Service]]): pass


# def InjectWithCondition(baseClass: type, fallback: list[type[Service]]): pass # FIXME: overload function does not work because theres already another with two variable


@overload
def BuildOnlyIf(flag: bool):
    def decorator(cls: Type[S]) -> Type[S]:
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
        if you dont want the built class to call the builder function simply remove from the dependency list
    """
    def decorator(cls: Type[S]) -> Type[S]:
        BuildOnlyIfDependencies[cls.__name__] = {
            DependencyConstant.BUILD_ONLY_CLASS_KEY: cls,
            DependencyConstant.BUILD_ONLY_DEP_KEY: None,
            DependencyConstant.BUILD_ONLY_FLAG_KEY: None,
            DependencyConstant.BUILD_ONLY_PARAMS_KEY: None,
            DependencyConstant.BUILD_ONLY_FUNC_KEY: func,
        }
        return cls
    return decorator


def SkipBuild(cls: Type[S]):
    decorator = BuildOnlyIf(cls)
    return decorator(False)


def PossibleDep(dependencies: list[type[Service]]):
    def decorator(cls: Type[S]) -> Type[S]:
        PossibleDependencies[cls.__name__] = [d.__name__ for d in dependencies]
        return cls
    return decorator


def OptionalDep(dependencies: list[type[Service]]):
    def decorator(cls: Type[S]) -> Type[S]:
        OptionalDependencies[cls.__name__] = [d.__name__ for d in dependencies]
        return cls
    return decorator