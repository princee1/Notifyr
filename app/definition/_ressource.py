"""
# The `BaseResource` class initializes with a `container` attribute assigned from the `CONTAINER`
# instance imported from `container`.
"""
from typing import Any, Callable, Iterable, Mapping, TypeVar
from interface.middleware import EventInterface
from services.assets_service import AssetService
from container import Get,Need
from definition._service import Service
from fastapi import APIRouter, HTTPException, Request, Response, status
from implements import Interface
from utils.prettyprint import PrettyPrinter_,PrettyPrinter
import time


T = TypeVar('T', bound=Service)
PATH_SEPARATOR = "/"


class Ressource(EventInterface):
    def __init__(self, prefix: str) -> None:
        self.prettyPrinter:PrettyPrinter = PrettyPrinter_
        if not prefix.startswith(PATH_SEPARATOR):
            prefix = PATH_SEPARATOR + prefix
        self.router = APIRouter(prefix,on_shutdown=self.on_shutdown,on_startup=self.on_startup)
        self._add_routes()

    def get(self, dep: type, scope=None, all=False) -> T:
        return Get(dep,scope,all)

    def need(self, dep: type) -> T:
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


class AssetRessource(Ressource):
    """
    Ressource with a direct reference to the AssetService
    """

    def __init__(self, prefix: str) -> None:
        super().__init__(prefix)
        self.assetService: AssetService = Get(AssetService)


def Handler(handler_function: Callable[[Callable, Iterable[Any], Mapping[str, Any]], Exception | None]):
    def decorator(func):
        def wrapper(*args, **kwargs):
            return handler_function(func, *args, **kwargs)
        return wrapper
    return decorator


def Guards(guard_function: Callable[[Iterable[Any], Mapping[str, Any]], tuple[bool, str]]):
    def decorator(func):
        def wrapper(*args, **kwargs):
            flag, message = guard_function(*args, **kwargs)
            if not flag:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail=message)
            return func(*args, **kwargs)
        return wrapper
    return decorator
