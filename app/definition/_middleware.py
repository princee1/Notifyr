import functools
from typing import Callable, Literal
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction
from starlette.datastructures import MutableHeaders,Headers
from enum import Enum
import asyncio
from fnmatch import fnmatch


METHODS = Literal['GET','POST','PATCH','PUT','DELETE','HEAD','OPTION']

MIDDLEWARE: dict[str, type] = {}
class MiddlewarePriority(Enum):

    PROCESS_TIME = 1
    LOAD_BALANCER= 2
    ANALYTICS = 3
    SECURITY = 4
    AUTH = 5
    USER_APP = 5.5
    CHALLENGE = 6
    BACKGROUND_TASK_SERVICE = 7


class MiddleWare(BaseHTTPMiddleware):

    def __init_subclass__(cls: type) -> None:
        MIDDLEWARE[cls.__name__] = cls
        #setattr(cls,'priority',None)

    async def dispatch(self, request:Request, call_next:Callable[[Request],Response]):
        return await call_next(request)

def path_matcher(paths: list[str], url: str) -> bool:
    if not paths:
        return True
    return any(fnmatch(url, pattern) for pattern in paths)

def exclude_path_matcher(paths: list[str], url: str) -> bool:
    if not paths:
        return True
    return not any(fnmatch(url, pattern) for pattern in paths)

def get_url(request:Request):
    base_url = str(request.base_url)
    url = str(request.url).replace(base_url,"")
    return "/" + url

def parse_urls(paths:list[str]):
    temp = []
    for path in paths:
        if not path.startswith('/'):
            path = '/' + path

        if path.endswith('/*'):
            path = path[0:-2] + "*"
        temp.append(path)
    return temp
            

def ApplyOn(paths:list[str]=['/*'],methods:list[METHODS]=[]):
    paths = parse_urls(paths)

    def decorator(func:Callable):

        @functools.wraps(func)
        async def wrapper(self:MiddleWare,request:Request,call_next:Callable[..., Response]):

            url = get_url(request)

            if not path_matcher(paths,url):
                return await call_next(request)

            if methods and request.method not in methods:
                return await call_next(request)
                  
            return await func(self,request,call_next)
        return wrapper
    return decorator

def ExcludeOn(paths:list[str]=['/*'],methods:list[METHODS]=[]):
    paths = parse_urls(paths)

    def decorator(func:Callable):
        @functools.wraps(func)
        async def wrapper(self:MiddleWare,request:Request,call_next:Callable[..., Response]):
            url = get_url(request)

            if not exclude_path_matcher(paths,url):
                return await call_next(request)
            
            if methods and request.method not in methods:
                return await call_next(request)
            
            return await func(self,request,call_next)       
        
        return wrapper
    return decorator

def OptionsRulesOn(options:list[Callable[[Request],bool]]=[]):
    def decorator(func:Callable):
        
        @functools.wraps(func)
        async def wrapper(self:MiddleWare,request:Request,call_next:Callable[..., Response]):

            for option in options:
                if asyncio.iscoroutinefunction(option):
                    if not await option(request):
                        return await call_next(request)            
                else:
                    if not option(request):
                        return await call_next(request)
            
            return await func(self,request,call_next)
            
        return wrapper
    
    return decorator

def BypassOn(bypass=True):
    def decorator(func:Callable):

        @functools.wraps(func)
        async def wrapper(self:MiddleWare,request:Request,call_next:Callable[..., Response]):
            if bypass:
                return await call_next(request)
            return await func(self,request,call_next)
        return wrapper
    
    return decorator


