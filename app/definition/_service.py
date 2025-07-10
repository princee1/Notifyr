import asyncio
from enum import Enum
import functools
from typing import Any, overload, Callable, Type, TypeVar, Dict
from app.utils.prettyprint import PrettyPrinter, PrettyPrinter_
from app.utils.constant import DependencyConstant
from app.utils.helper import issubclass_of
import warnings
import datetime as dt
from typing import TypedDict

from aiorwlock import RWLock


AbstractDependency: Dict[str, dict] = {}
AbstractServiceClasses: Dict[str, type] = {}
BuildOnlyIfDependencies: Dict = {}
PossibleDependencies: Dict[str, list[type]] = {}
OptionalDependencies: Dict[str, list[type]] = {}
__CLASS_DEPENDENCY:Dict[str,type]= {}
__DEPENDENCY: list[type] = []


class ServiceStatus(Enum):
    AVAILABLE = 1
    NOT_AVAILABLE = 2
    TEMPORARY_NOT_AVAILABLE=3
    PARTIALLY_AVAILABLE = 4
    WORKS_ALMOST_ATT = 5

class StateProtocol(TypedDict):
    service:str
    status:int
    to_build:bool = False
    to_destroy:bool =False


class BuildErrorLevel(Enum):
    ABORT = 4
    FAILURE = 3
    WARNING = 2
    SKIP = 1


class BuildError(BaseException):
    def __init__(self,service ,*args: object) -> None:
        super().__init__(*args)
        self.service = service
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


class BuildNotImplementedError(BuildError):
    ...


#################################            #####################################

class ServiceNotAvailableError(BuildError):
    pass

class ServiceTemporaryNotAvailableError(BuildError):
    pass

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


#################################            #####################################

WAIT_TIME = 0.1

class BaseService():

    def __init__(self) -> None:
        self.build_status: BuildErrorLevel = None
        self._builded: bool = False
        self._destroyed: bool = False
        self.prettyPrinter: PrettyPrinter = PrettyPrinter_
        self.service_status: ServiceStatus = None
        self.method_not_available: list[str] = []
        self.service_list:list[BaseService] = []
        self.statusLock = RWLock()
        self.stateCounter = 0


    @property
    def is_reader_locked(self)->bool:
        return self.statusLock.reader_lock.locked
    
    @staticmethod
    def CheckStatusBeforeHand(func:Callable):
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            
            self:BaseService = args[0]

            if self.is_reader_locked:
                raise ServiceChangingStateError
    
            match self.service_status :
                case ServiceStatus.NOT_AVAILABLE :
                    raise ServiceNotAvailableError
                case ServiceStatus.TEMPORARY_NOT_AVAILABLE:
                    raise ServiceTemporaryNotAvailableError
                case _:
                    ...

            if not self._builded  or self._destroyed:
                raise ServiceNotAvailableError

            if func.__name__ in self.method_not_available:
                raise MethodServiceNotAvailableError

            return func(*args, **kwargs)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            
            self:BaseService = args[0]

            async with self.statusLock.reader as lock:

                match self.service_status :
                    case ServiceStatus.NOT_AVAILABLE :
                        raise ServiceNotAvailableError
                    case ServiceStatus.TEMPORARY_NOT_AVAILABLE:
                        raise ServiceTemporaryNotAvailableError
                    case _:
                        ...

                if not self._builded  or self._destroyed:
                    raise ServiceNotAvailableError

                if func.__name__ in self.method_not_available:
                    raise MethodServiceNotAvailableError

            return await func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else  sync_wrapper

    def verify_dependency(self):
        """
        Callback to check if the state of the service dependency is suffisant to run
        """
        ...

    @CheckStatusBeforeHand
    async def async_pingService(self):
        ...
    
    @CheckStatusBeforeHand
    def sync_pingService(self):
        ...

    
    def build(self):
        # warnings.warn(
        #     f"This method from the service class {self.__class__.__name__} has not been implemented yet.", UserWarning, 2)
        raise BuildNotImplementedError

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

    def check_service(self):
        """
        Callback to check internally if the state of the service is suffisant to run
        """
        ...
    
    # TODO Dependency that use service with failed might not properly, need to handle the view
    def _builder(self):
        try:
            now = dt.datetime.now()
            self.check_service()
            self.verify_dependency()
            self.build()
            self._builded = True
            self._destroyed = False
            self.prettyPrinter.success(
                f'[{now}] Successfully built the service: {self.__class__.__name__}', saveable=True)
            self.prettyPrinter.wait(WAIT_TIME, False)
            self.service_status = ServiceStatus.AVAILABLE

        except BuildFailureError as e:
            self.prettyPrinter.error(
                f'[{now}] Error while building the service: {self.__class__.__name__}. Service using this dependency will not function properly', saveable=True)
            self.service_status = ServiceStatus.NOT_AVAILABLE
            pass

        except BuildAbortError as e:
            self.prettyPrinter.error(
                f'[{now}] Error while building the service: {self.__class__.__name__}. Aborting the process', saveable=True)
            exit(-1)

        except BuildWarningError as e:
            # TODO might to change the color because of the error since, it will be for malfunction dependent service
            self.prettyPrinter.warning(
                f'[{now}] Warning issued while building: {self.__class__.__name__}. Service might malfunction properly', saveable=True)
            self.service_status = ServiceStatus.WORKS_ALMOST_ATT

        
        except BuildSkipError as e: # TODO change color
            self.prettyPrinter.info(
                f'[{now}] Slight Problem encountered while building the service: {self.__class__.__name__}', saveable=True)
            self.service_status = ServiceStatus.WORKS_ALMOST_ATT
            pass

        except BuildNotImplementedError as e:
            self.prettyPrinter.warning( # TODO change color
                f'[{now}] Service Not Implemented Yet: {self.__class__.__name__} ', saveable=True)
            self.prettyPrinter.wait(WAIT_TIME, False)
            self.service_status = ServiceStatus.NOT_AVAILABLE

        except Exception as e:
            print(e)
            print(e.__class__)
            self.prettyPrinter.error(
                f'[{now}] Error while building the service: {self.__class__.__name__}. Aborting the process', saveable=True)
            exit(-1)    


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
    
    @property
    def services_status(self):
        return {s:s.service_status for s in self.service_list}


S = TypeVar('S', bound=BaseService)


def AbstractServiceClass(cls: S) -> S:
    if cls in __DEPENDENCY:
        __DEPENDENCY.remove(cls)
    AbstractServiceClasses[cls.__name__] = cls

    return cls


def Service(cls: Type[S]) -> Type[S]:
    if cls.__name__ not in AbstractServiceClasses and cls not in __DEPENDENCY:
        __DEPENDENCY.append(cls)
        __CLASS_DEPENDENCY[cls.__name__] = cls
    return cls


@overload
def InjectWithCondition(baseClass: type, resolvedClass: type[BaseService]):
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
            raise BuildAbortError(f'Base class {baseClass} not an abstract service')
        if not issubclass_of(BaseService, baseClass):
            raise BuildAbortError(f'Base class {baseClass} is not class of Service')
        if not issubclass_of(BaseService, cls):
            raise BuildAbortError(f'Class {cls} is not class of Service')
        AbstractDependency[cls.__name__] = {baseClass.__name__: {DependencyConstant.RESOLVED_FUNC_KEY: resolvedClass,
                                                                 DependencyConstant.RESOLVED_PARAMETER_KEY: None,
                                                                 DependencyConstant.RESOLVED_DEPS_KEY: None,
                                                                 DependencyConstant.RESOLVED_CLASS_KEY: None}}
        return cls
    return decorator


@overload
def InjectWithCondition(baseClass: type[BaseService], resolvedClass: Callable[..., type[BaseService]],
                        fallback: list[type[BaseService]]): pass


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


def PossibleDep(dependencies: list[type[BaseService]]):
    def decorator(cls: Type[S]) -> Type[S]:
        PossibleDependencies[cls.__name__] = [d.__name__ for d in dependencies]
        return cls
    return decorator


def OptionalDep(dependencies: list[type[BaseService]]):
    def decorator(cls: Type[S]) -> Type[S]:
        OptionalDependencies[cls.__name__] = [d.__name__ for d in dependencies]
        return cls
    return decorator
