from typing import Callable
from app.utils.dependencies import APIFilterInject
from enum import Enum

class DecoratorPriority(Enum):
    PERMISSION = 1
    GUARD = 2
    PIPE = 3
    HANDLER = 4
    INTERCEPTOR = 5


class NextHandlerException(Exception):
    ...


class DecoratorObj:

    def __init__(self, ref_callback: Callable, filter=True):
        self.ref = ref_callback
        self.filter = filter

    def do(self, *args, **kwargs):
        if self.filter:
            return APIFilterInject(self.ref)(*args, **kwargs)
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

    def handle(self, function: Callable, *args, **kwargs):
        ...

    def last_resort_handling(self):
        """
        :raise: `NextHandlerException` if the go_to_default_exception is `False`
        :raise: `HandlerDefaultException` if the go_to_default_exception is `True`
        """
        if not self.go_to_default_exception:
            raise NextHandlerException
        
        raise HandlerDefaultException


class HandlerDefaultException(Exception):
    ...


class Pipe(DecoratorObj):
    def __init__(self, before: bool):
        self.before = before
        super().__init__(self.pipe, filter=before)

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
        super().__init__(self.intercept_before, True)

    def intercept_before(self):
        ...
    
    def intercept_after(self):
        ...
    

class InterceptorDefaultException(Exception):
    ...
