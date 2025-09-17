import asyncio
from typing import Any, Callable

from fastapi import Response
from app.utils.helper import APIFilterInject,AsyncAPIFilterInject
from asgiref.sync import sync_to_async
from enum import Enum

class DecoratorPriority(Enum):
    PERMISSION = 1
    HANDLER = 2
    PIPE = 3
    GUARD = 4
    INTERCEPTOR = 5


class NextHandlerException(Exception):
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

    def guard(self) -> tuple[tuple, dict]:
        ...


class GuardDefaultException(Exception):
    ...

class Handler(DecoratorObj):
    def __init__(self,go_to_default_exception:bool = False):
        super().__init__(self.handle, False)
        self.go_to_default_exception = go_to_default_exception

    async def do(self, *args, **kwargs):
        return await self.ref(*args, **kwargs)

    async def handle(self, function: Callable, *args, **kwargs):
        return await function(*args,**kwargs)

class HandlerDefaultException(Exception):
    ...


class Pipe(DecoratorObj):
    def __init__(self, before: bool):
        self.before = before
        super().__init__(self.pipe, filter=True)

    def pipe(self):
        ...


class PipeDefaultException(Exception):
    ...


class Permission(DecoratorObj):

    def __init__(self,):
        super().__init__(self.permission, True)

    def permission(self,):
        ...


class PermissionDefaultException(Exception):
    ...

class Interceptor(DecoratorObj):

    def __init__(self,):
        super().__init__(self.intercept, True)


    def _intercept_before(self):
        ...
    
    def _intercept_after(self,result:Response|Any):
        ...
    
    async def intercept(self,function:Callable,*args,**kwargs):
        if asyncio.iscoroutinefunction(self._intercept_before):
            await  AsyncAPIFilterInject(self._intercept_before)(*args,**kwargs)
        else:
            APIFilterInject(self._intercept_before)(*args,**kwargs)

        result = await function(*args,**kwargs)
        if asyncio.iscoroutinefunction(self._intercept_after):
            await self._intercept_after(result)
        else:
            self._intercept_after(result)
        return result
    
    async def do(self,function:Callable, *args, **kwargs):
        return await self.intercept(function,*args,**kwargs)

class InterceptorDefaultException(Exception):
    ...
