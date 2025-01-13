from typing import Callable
from utils.dependencies import APIFilterInject
from enum import Enum

class DecoratorPriority(Enum):
    PERMISSION = 1
    GUARD = 2
    PIPE = 3
    HANDLER = 4


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
    def __init__(self):
        super().__init__(self.handle, False)

    def handle(self, function: Callable, *args, **kwargs):
        ...


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
        super().__init__(self.intercept, True)

    def intercept(self):
        ...

class InterceptorDefaultException(Exception):
    ...
