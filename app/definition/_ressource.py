"""
# The `BaseResource` class initializes with a `container` attribute assigned from the `CONTAINER`
# instance imported from `container`.
"""
from typing import Any, Callable, Iterable, Mapping, TypeVar, Type
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


PATH_SEPARATOR = "/"

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

    @property
    def routeExample(self):
        pass


def Handler(handler_function: Callable[[Callable, Iterable[Any], Mapping[str, Any]], Exception | None]):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return handler_function(func, *args, **kwargs)
        return wrapper
    return decorator


def Guards(guard_function: Callable[[Iterable[Any], Mapping[str, Any]], tuple[bool, str]]):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            flag, message = guard_function(*args, **kwargs)
            if not flag:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail=message)
            return func(*args, **kwargs)
        return wrapper
    return decorator

