"""
# The `BaseResource` class initializes with a `container` attribute assigned from the `CONTAINER`
# instance imported from `container`.
"""
from inspect import isclass
from typing import Any, Callable, Dict, Iterable, Mapping, TypeVar, Type
from interface.middleware import EventInterface
from services.assets_service import AssetService
from container import Get, Need
from definition._service import S, Service
from fastapi import APIRouter, HTTPException, Request, Response, status
from implements import Interface
from utils.prettyprint import PrettyPrinter_, PrettyPrinter
import time
import functools
from utils.helper import getParentClass
from fastapi import BackgroundTasks


PATH_SEPARATOR = "/"


class MethodStartsWithError(Exception):
    ...

RESSOURCES:dict[str,type] = {}

class Ressource(EventInterface):

    def __init_subclass__(cls: Type) -> None:
        RESSOURCES[cls.__name__] = cls

    def __init__(self, prefix: str) -> None:
        self.assetService: AssetService = Get(AssetService)
        self.prettyPrinter: PrettyPrinter = PrettyPrinter_
        if not prefix.startswith(PATH_SEPARATOR):
            prefix = PATH_SEPARATOR + prefix
        self.router = APIRouter(prefix=prefix, on_shutdown=[
                                self.on_shutdown], on_startup=[self.on_startup])
        self._add_routes()

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
        pass

    def _add_event(self):
        ...

    

    @property
    def routeExample(self):
        pass

R = TypeVar('R', bound=Ressource)


def common_class_decorator(cls:Type[R]|Callable,decorator:Callable,handling_func:Callable,start_with:str = None)->Type[R]|Callable:
    if type(cls) == type and isclass(cls):
            if start_with is None:
                raise MethodStartsWithError("start_with is required for class")
            for attr in dir(cls):
                if callable(getattr(cls, attr)) and attr.startswith(start_with):
                    handler = getattr(cls,attr)
                    setattr(cls,attr,decorator(handling_func)(handler))
            return cls
    return None



def Handler(handler_function: Callable[[Callable, Iterable[Any], Mapping[str, Any]], Exception | None],start_with:str = None):
    def decorator(func:Type[R]| Callable) -> Type[R]| Callable:
        data = common_class_decorator(func,Handler,handler_function,start_with)
        if data != None:
            return data
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return handler_function(func, *args, **kwargs)
        return wrapper
    return decorator


def Guard(guard_function: Callable[[Iterable[Any], Mapping[str, Any]], tuple[bool, str]],start_with:str = None):
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


def Pipe(pipe_function: Callable[[Iterable[Any], Mapping[str, Any]], tuple[Iterable[Any], Mapping[str, Any]]],before:bool = True, start_with:str = None):
    def decorator(func: Type[R]|Callable) -> Type[R]|Callable:
        data = common_class_decorator(func,Pipe,pipe_function,start_with)
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


def Interceptor(interceptor_function: Callable[[Iterable[Any], Mapping[str, Any]], Type[R]|Callable],start_with:str = None):
    def decorator(func: Type[R]|Callable) -> Type[R]|Callable:
        data = common_class_decorator(func,Interceptor,interceptor_function,start_with)
        if data != None:
            return data
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return interceptor_function(func,*args, **kwargs)
        return wrapper
    return decorator