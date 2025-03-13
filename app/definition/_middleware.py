import functools
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction
from starlette.datastructures import MutableHeaders,Headers
from enum import Enum

MIDDLEWARE: dict[str, type] = {}
class MiddlewarePriority(Enum):

    PROCESS_TIME = 1
    ANALYTICS = 2
    SECURITY = 3
    AUTH = 4
    BACKGROUND_TASK_SERVICE = 5


class MiddleWare(BaseHTTPMiddleware):

    def __init_subclass__(cls: type) -> None:
        MIDDLEWARE[cls.__name__] = cls
        #setattr(cls,'priority',None)
    
def ApplyOn(paths:list[str],exclude:list[str]=[],methods:list[str]=[],options:list[Callable[...,bool]]=[]   ):
    def decorator(func:Callable):

        @functools.wraps(func)
        async def wrapper(self:MiddleWare,request:Request,call_next:Callable[..., Response]):
            base_url = str(request.base_url)
            url = str(request.url).replace(base_url,"")

            if url==base_url:
                return await func(self,request,call_next)

            return await call_next(request)
        return wrapper
    return decorator
