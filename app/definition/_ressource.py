"""
The `BaseResource` class initializes with a `container` attribute assigned from the `CONTAINER`
instance imported from `container`.
"""
from inspect import isclass
from typing import Any, Callable, Dict, Iterable, Mapping, TypeVar, Type
from services.assets_service import AssetService
from services.security_service import JWTAuthService
from container import Get, Need
from definition._service import S, Service
from fastapi import APIRouter, HTTPException, Request, Response, status
from utils.prettyprint import PrettyPrinter_, PrettyPrinter
import time
import functools
from utils.helper import getParentClass
from fastapi import BackgroundTasks
from interface.events import EventInterface


PATH_SEPARATOR = "/"
DEFAULT_STARTS_WITH = '_api_'

def get_class_name_from_method(func: Callable) -> str:
    return func.__qualname__.split('.')[0]

class MethodStartsWithError(Exception):
    ...

RESSOURCES:dict[str,type] = {}
PROTECTED_ROUTES:dict[str,list[str]] = {}
ROUTES:dict[str,list[dict]] = {  }
METADATA_ROUTES:dict[str,str] = {}

def add_protected_route_metadata(class_name:str,method_name:str,):
    if class_name in PROTECTED_ROUTES:
        PROTECTED_ROUTES[class_name].append(method_name)
    else:
        PROTECTED_ROUTES[class_name] = [method_name]

class Ressource(EventInterface):

    @staticmethod
    def _build_operation_id(route_name:str,method_name:str,operation_id:str)->str:
        if operation_id != None:
            return operation_id

        return route_name.replace(PATH_SEPARATOR, "_")

    @staticmethod
    def AddRoute(path:str,methods:Iterable[str] = ['POST'],operation_id:str = None,response_model:Any = None):
        def decorator(func:Callable):
            computed_operation_id = Ressource._build_operation_id(path,func.__qualname__,operation_id) 
            METADATA_ROUTES[func.__qualname__] = computed_operation_id
            # TODO put the add route logic on the static scope
            class_name = get_class_name_from_method(func)
            kwargs = {
                'path':path,
                'endpoint':func.__name__,
                'operation_id':operation_id,
                'summary':func.__doc__,
                'response_model':response_model,
                'methods':methods,

            }
            if class_name not in ROUTES:
                ROUTES[class_name] = []

            ROUTES[class_name].append(kwargs)

            @functools.wraps(func)
            def wrapper(*args,**kwargs):
                return func(*args,**kwargs)
            return  wrapper
        return decorator

    def __init_subclass__(cls: Type) -> None:
        RESSOURCES[cls.__name__] = cls
        #ROUTES[cls.__name__] = []

    def __init__(self, prefix: str) -> None:
        self.assetService: AssetService = Get(AssetService)
        self.prettyPrinter: PrettyPrinter = PrettyPrinter_
        if not prefix.startswith(PATH_SEPARATOR):
            prefix = PATH_SEPARATOR + prefix
        self.router = APIRouter(prefix=prefix, on_shutdown=[
                                self.on_shutdown], on_startup=[self.on_startup])
        self._add_routes()
        self._add_handcrafted_routes()
        self.default_response: Dict[int | str, Dict[str, Any]] | None = None

    def get(self, dep: Type[S], scope=None, all=False) -> Type[S]:
        return Get(dep, scope, all)

    def need(self, dep: Type[S]) -> Type[S]:
        return Need(dep)

    def on_startup(self):
        
        pass

    def on_shutdown(self):
        pass

    def _add_routes(self):
        routes_metadata = ROUTES[self.__class__.__name__]
        for route in routes_metadata:
            kwargs = route.copy()
            kwargs['endpoint'] = getattr(self, kwargs['endpoint'],)
            self.router.add_api_route(**kwargs)

    def _add_handcrafted_routes(self):
        ...

    def _add_event(self):
        ...
    
    @property
    def routeExample(self):
        pass

R = TypeVar('R', bound=Ressource)


def common_class_decorator(cls:Type[R]|Callable,decorator:Callable,handling_func:Callable,start_with:str,**kwargs)->Type[R] | None:
    if type(cls) == type and isclass(cls):
            if start_with is None:
                raise MethodStartsWithError("start_with is required for class")
            for attr in dir(cls):
                if callable(getattr(cls, attr)) and attr.startswith(start_with):
                    handler = getattr(cls,attr)
                    if handling_func == None:
                        setattr(cls,attr,decorator(**kwargs)(handler))
                    else:
                        setattr(cls,attr,decorator(handling_func,**kwargs)(handler))
            return cls
    return None


TOKEN_NAME_PARAMETER = 'token_'
CLIENT_IP_PARAMETER = 'client_ip_'

def Permission(start_with:str  = DEFAULT_STARTS_WITH):
   
    def decorator(func: Type[R]|Callable) -> Type[R]|Callable:
        data = common_class_decorator(func,Permission,None,start_with)
        if data != None:
            return data
        
        func_name = func.__name__
        class_name = get_class_name_from_method(func)
        add_protected_route_metadata(class_name,func_name)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            print(func_name)
            if len(kwargs) < 2:
                raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
            try:
                token = kwargs[TOKEN_NAME_PARAMETER]
                issued_for = kwargs[CLIENT_IP_PARAMETER]
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
        
            jwtService:JWTAuthService = Get(JWTAuthService)
            if jwtService.verify_permission(token, class_name, func_name,issued_for): # TODO Need to replace the function name with the metadata mapping
                return func(*args, **kwargs)
        return wrapper
    return decorator


def Handler(handler_function: Callable[[Callable, Iterable[Any], Mapping[str, Any]], Exception | None],start_with:str = DEFAULT_STARTS_WITH):
    def decorator(func:Type[R]| Callable) -> Type[R]| Callable:
        data = common_class_decorator(func,Handler,handler_function,start_with)
        if data != None:
            return data
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return handler_function(func, *args, **kwargs)
        return wrapper
    return decorator


def Guard(guard_function: Callable[[Iterable[Any], Mapping[str, Any]], tuple[bool, str]],start_with:str = DEFAULT_STARTS_WITH):
    def decorator(func: Callable| Type[R])-> Callable| Type[R]:
        data = common_class_decorator(func,Guard,guard_function,start_with)
        if data != None:
            return data
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            flag, message = guard_function(*args, **kwargs)
            if not flag:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail=message)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def Pipe(pipe_function: Callable[[Iterable[Any], Mapping[str, Any]], tuple[Iterable[Any], Mapping[str, Any]]],before:bool = True, start_with:str = DEFAULT_STARTS_WITH):
    def decorator(func: Type[R]|Callable) -> Type[R]|Callable:
        data = common_class_decorator(func,Pipe,pipe_function,start_with,before=before)
        if data != None:
            return data
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if before:
                args,kwargs = pipe_function(*args, **kwargs)
                return func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                return pipe_function(result)
        return wrapper
    return decorator


def Interceptor(interceptor_function: Callable[[Iterable[Any], Mapping[str, Any]], Type[R]|Callable],start_with:str = DEFAULT_STARTS_WITH):
    def decorator(func: Type[R]|Callable) -> Type[R]|Callable:
        data = common_class_decorator(func,Interceptor,interceptor_function,start_with)
        if data != None:
            return data
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return interceptor_function(func,*args, **kwargs)
        return wrapper
    return decorator