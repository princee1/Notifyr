import asyncio
from typing import Any, Callable

from fastapi import HTTPException, Response
from app.utils.helper import APIFilterInject,AsyncAPIFilterInject
from asgiref.sync import sync_to_async
from enum import Enum

class DecoratorPriority(Enum):
    LIMITER = 0
    PERMISSION = 1
    HANDLER = 2
    PIPE = 3
    GUARD = 4
    INTERCEPTOR = 5

class DecoratorException(Exception):

    def __init__(self,status_code=None,details:Any=None,headers:dict[str,str]=None, *args):
        super().__init__(*args)
        self.status_code = status_code
        self.details = details
        self.headers=headers

    def raise_http_exception(self):
        if self.status_code == None:
            return
        
        raise HTTPException(self.status_code,self.details,self.headers)
        


class NextHandlerException(DecoratorException):
    ...


class DecoratorObj:

    def __init__(self, ref_callback: Callable, filter=True):
        self.ref = ref_callback
        self.filter = filter
        self.is_async = asyncio.iscoroutinefunction(self.ref)

    async def do(self, *args, **kwargs):
        if self.filter:
            if self.is_async:
                return await AsyncAPIFilterInject(self.ref)(*args, **kwargs)
            return APIFilterInject(self.ref)(*args, **kwargs)
        if self.is_async:
            return await self.ref(*args, **kwargs)
        return self.ref(*args, **kwargs)


class Guard(DecoratorObj):

    def __init__(self):
        super().__init__(self.guard, True)

    def guard(self) -> tuple[bool, str]:
        ...


class GuardDefaultException(DecoratorException):
    ...

class Handler(DecoratorObj):
    def __init__(self,go_to_default_exception:bool = False):
        super().__init__(self.handle, False)
        self.go_to_default_exception = go_to_default_exception

    async def do(self, *args, **kwargs):
        return await self.ref(*args, **kwargs)

    async def handle(self, function: Callable, *args, **kwargs):
        return await function(*args,**kwargs)

class HandlerDefaultException(DecoratorException):
    ...


class Pipe(DecoratorObj):
    def __init__(self, before: bool):
        self.before = before
        super().__init__(self.pipe, filter=True)

    def pipe(self):
        ...


class PipeDefaultException(DecoratorException):
    ...


class Permission(DecoratorObj):

    def __init__(self,):
        super().__init__(self.permission, True)

    def permission(self,):
        ...


class PermissionDefaultException(DecoratorException):
    ...

class Interceptor(DecoratorObj):

    def __init__(self,):
        super().__init__(self.intercept, True)


    def _before(self):
        ...
    
    def _after(self,result:Response|Any):
        ...
    
    async def intercept(self,function:Callable,*args,**kwargs):
        r = APIFilterInject(self._before)(*args,**kwargs)
        if asyncio.iscoroutinefunction(self._before):
            await r
            
        result = await function(*args,**kwargs)
        r= APIFilterInject(self._after)(result,**kwargs)
        if asyncio.iscoroutinefunction(self._after):
            await  r

        return result
    
    async def do(self,function:Callable, *args, **kwargs):
        return await self.intercept(function,*args,**kwargs)

class InterceptorDefaultException(DecoratorException):
    ...
