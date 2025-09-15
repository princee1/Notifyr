import asyncio
from enum import Enum
import functools
from typing import Any, Literal, overload, Callable, Type, TypeVar, Dict
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
_CLASS_DEPENDENCY:Dict[str,type]= {}
__DEPENDENCY: list[type] = []


DEFAULT_BUILD_STATE = -1
DEFAULT_DESTROY_STATE = -1


class ServiceStatus(Enum):
    AVAILABLE = 1
    """
    The service is fully operational and available for use.
    """
    NOT_AVAILABLE = 2
    """
    The service is not available and cannot be used."""
    TEMPORARY_NOT_AVAILABLE=3
    """
    The service is temporarily not available, possibly due to maintenance or transient issues."""
    PARTIALLY_AVAILABLE = 4
    """
    The service is operational but may have some limitations or issues that affect its performance or reliability."""
    WORKS_ALMOST_ATT = 5
    """
    The service is operational but may have some features or functionalities that are not fully working as expected, potentially leading to minor issues or inconveniences for users.
    """
    MAJOR_SYSTEM_FAILURE=6
    """
    The fact that the service does not work will not permit the program to properly run
    """


class Report(TypedDict):
    service: str
    status: str
    timestamp: str
    reason: str | None= None
    variables: dict[str,Any] | None= None

PROCESS_SERVICE_REPORT:dict[str, list[Report]] = {}


class StateProtocol(TypedDict):
    service:str
    status:int | None = None
    to_build:bool = False
    to_destroy:bool =False
    callback_state_function:str = None
    build_state:int = DEFAULT_BUILD_STATE
    destroy_state:int = DEFAULT_DESTROY_STATE
    force_sync_verify:bool = False
    bypass_async_verify:bool = False

class VariableProtocol(TypedDict):
    service:str
    variables:dict[str,Any] = None
    variables_function:str = None

class BuildReport(TypedDict):
    ...

class BuildErrorLevel(Enum):
    ABORT = 4
    FAILURE = 3
    WARNING = 2
    SKIP = 1


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


class BuildSkipError(BuildError):
    pass


class BuildFallbackError(BuildError):
    pass


class BuildNotImplementedError(BuildError):
    ...


STATUS_TO_ERROR_MAP = {
    ServiceStatus.NOT_AVAILABLE: BuildFailureError,
    ServiceStatus.TEMPORARY_NOT_AVAILABLE: BuildWarningError,
    ServiceStatus.PARTIALLY_AVAILABLE: BuildWarningError,
    ServiceStatus.WORKS_ALMOST_ATT: BuildSkipError,
    ServiceStatus.MAJOR_SYSTEM_FAILURE:BuildAbortError
}

#################################            #####################################

class ServiceNotAvailableError(BuildError):
    pass

class MajorSystemFailureError(BufferError):
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

class ServiceDoesNotExistError(BuildError):
    ...

class StateProtocolMalFormattedError(BuildError):
    ...

#################################            #####################################

WAIT_TIME = .1

class BaseService():
    CONTEXT:Literal['sync','async'] = 'sync'

    def __init__(self) -> None:
        self.build_status: BuildErrorLevel = None
        self._builded: bool = False
        self._destroyed: bool = False
        self.prettyPrinter: PrettyPrinter = PrettyPrinter_
        self.service_status: ServiceStatus = None
        self.method_not_available: set[str] = set()
        self.dependant_services:dict[Type[BaseService],BaseService] = {}
        self.statusLock = RWLock()
        self.stateCounter = 0

        self.pretty_print_wait_time = WAIT_TIME

    @property
    def is_reader_locked(self)->bool:
        return self.statusLock.reader_lock.locked
    

    def check_status(self,func_name):
        match self.service_status :

            case ServiceStatus.MAJOR_SYSTEM_FAILURE:
                raise MajorSystemFailureError

            case ServiceStatus.NOT_AVAILABLE :
                raise ServiceNotAvailableError
            case ServiceStatus.TEMPORARY_NOT_AVAILABLE:
                raise ServiceTemporaryNotAvailableError
            case _:
                ...

        if not self._builded  or self._destroyed:
            raise ServiceNotAvailableError

        if func_name in self.method_not_available:
            raise MethodServiceNotAvailableError

    @staticmethod
    def CheckStatusBeforeHand(func:Callable):
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            
            self:BaseService = args[0]

            if self.is_reader_locked:
                raise ServiceChangingStateError
    
            self.check_status(func.__name__)
            return func(*args, **kwargs)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            
            self:BaseService = args[0]

            async with self.statusLock.reader as lock:

                self.check_status(func.__name__)
            return await func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else  sync_wrapper

    async def async_verify_dependency(self):
        """
        Callback to check if the state of the service dependency is suffisant to run
        """
        self.method_not_available = set()

    def verify_dependency(self):
        """
        Callback to check if the state of the service dependency is suffisant to run
        """
        self.method_not_available = set()
        

    @CheckStatusBeforeHand
    async def async_pingService(self,**kwargs):
        ...
    
    @CheckStatusBeforeHand
    def sync_pingService(self,**kwargs):
        ...


    def build(self,build_state:int=DEFAULT_BUILD_STATE):
        # warnings.warn(
        #     f"This method from the service class {self.__class__.__name__} has not been implemented yet.", UserWarning, 2)
        raise BuildNotImplementedError(f"{self.name} not implemented")

    def destroy(self,destroy_state:int=DEFAULT_DESTROY_STATE):
        warnings.warn(
            f"This method from the service class {self.__class__.__name__} has not been implemented yet.", UserWarning, 2)
        pass

    def log(self):
        pass

    def __repr__(self) -> str:
        return super().__repr__()

    def __str__(self) -> str:
        return f"Service: {self.__class__.__name__} Hash: {self.__hash__()}"

    def report(self,state:Literal['destroy','build','variable']='build',variables:dict[str,Any]=None,reason:str=None, state_value:int=None):
        
        if self.name not in PROCESS_SERVICE_REPORT:
            PROCESS_SERVICE_REPORT[self.name] = []

        PROCESS_SERVICE_REPORT[self.name].append({
            'timestamp': dt.datetime.now().isoformat(),
            'state_name': state,
            'status': self.service_status.name,
            'variables': variables,
            'reason': reason,
            'state_value': state_value
        })
        pass
    
    # TODO Dependency that use service with failed might not properly, need to handle the view
    def _builder(self,quiet:bool=False,build_state:int = -1,force_sync_verify:bool=False):
        try:
            now = dt.datetime.now()
            
            if self.CONTEXT == 'sync' or force_sync_verify:
                self.method_not_available = set()
                self.verify_dependency()
            
            self.build(build_state=build_state)
            self._builded = True
            self._destroyed = False

            self.service_status = self.service_status if self.service_status != None else ServiceStatus.AVAILABLE
            
            if self.service_status in STATUS_TO_ERROR_MAP:
                if not quiet:
                    raise STATUS_TO_ERROR_MAP[self.service_status](f'Service {self.__class__.__name__} has status {self.service_status} after build')
            else:
                if not quiet:
                    self.prettyPrinter.success(
                        f'[{now}] Successfully built the service: {self.__class__.__name__}', saveable=True)
            if not quiet:
                self.prettyPrinter.wait(self.pretty_print_wait_time, False)
            
            reason = 'Service Built'
        except BuildFailureError as e:
            self.prettyPrinter.error(
                f'[{now}] Error while building the service: {self.__class__.__name__}. Service using this dependency will not function properly', saveable=True)
            self.service_status = ServiceStatus.NOT_AVAILABLE
            reason = 'Service not Built' if len(e.args) == 0 else e.args[0]

        except BuildAbortError as e:
            self.prettyPrinter.error(
                f'[{now}] Error while building the service: {self.__class__.__name__}. Aborting the process', saveable=True)
            print(e)
            reason = 'Service not Built' if len(e.args) == 0 else e.args[0]
            self.service_status = ServiceStatus.MAJOR_SYSTEM_FAILURE
            exit(-1)

        except BuildWarningError as e:
            # TODO might to change the color because of the error since, it will be for malfunction dependent service
            self.prettyPrinter.warning(
                f'[{now}] Warning issued while building: {self.__class__.__name__}. Service might malfunction properly', saveable=True)
            self.service_status = ServiceStatus.PARTIALLY_AVAILABLE
            reason = 'Service not Built' if len(e.args) == 0 else e.args[0]
        
        except BuildSkipError as e: # TODO change color
            self.prettyPrinter.info(
                f'[{now}] Slight Problem encountered while building the service: {self.__class__.__name__}', saveable=True)
            self.service_status = ServiceStatus.WORKS_ALMOST_ATT
            reason = 'Service not Built' if len(e.args) == 0 else e.args[0]

            pass

        except BuildNotImplementedError as e:
            self.prettyPrinter.warning( # TODO change color
                f'[{now}] Service Not Implemented Yet: {self.__class__.__name__} ', saveable=True)
            self.prettyPrinter.wait(WAIT_TIME, False)
            self.service_status = ServiceStatus.NOT_AVAILABLE
            reason = 'Service not Built' if len(e.args) == 0 else e.args[0]

        except Exception as e:
            print(e)
            print(e.__class__)
            self.prettyPrinter.error(
                f'[{now}] Error while building the service: {self.__class__.__name__}. Aborting the process', saveable=True)
            reason = 'Service not Built' if len(e.args) == 0 else e.args[0]
            self.service_status = ServiceStatus.MAJOR_SYSTEM_FAILURE
            exit(-1)    


        finally:
            self.report(reason=reason,state_value=build_state)

    def _destroyer(self,quiet:bool=False,destroy_state:int = DEFAULT_DESTROY_STATE):
        try:
            self.destroy(destroy_state=destroy_state)
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
            self.report('destroy',reason='Service Destroyed' if self._destroyed else 'Service Not Destroyed',state_value=destroy_state)
    
    @property
    def dependant_services_status(self):
        return {c:s.service_status for c,s in self.dependant_services.items()}

    @property
    def name(self):
        return self.__class__.__name__


S = TypeVar('S', bound=BaseService)


def AbstractServiceClass(cls: S) -> S:
    if cls in __DEPENDENCY:
        __DEPENDENCY.remove(cls)
    AbstractServiceClasses[cls.__name__] = cls

    return cls


def Service(cls: Type[S]) -> Type[S]:
    if cls.__name__ not in AbstractServiceClasses and cls not in __DEPENDENCY:
        __DEPENDENCY.append(cls)
        _CLASS_DEPENDENCY[cls.__name__] = cls
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
        def build(self,build_state=-1):
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
