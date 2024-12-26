from services.security_service import SecurityService
from container import InjectInMethod
from fastapi import Request, Response, FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction
from typing import Any, Awaitable, Callable, MutableMapping
import time
from interface.middleware import EventInterface, InjectableMiddlewareInterface



MIDDLEWARE: dict[str, type] = {

}


class MiddleWare(BaseHTTPMiddleware):
    def __init_subclass__(cls: type) -> None:
        MIDDLEWARE[cls.__name__] = cls


class ProcessTimeMiddleWare(MiddleWare):

    def __init__(self, app, dispatch=None) -> None:
        super().__init__(self, app, dispatch)

    async def dispatch(self, request: Request, call_next: Callable[..., Response]):
        start_time = time.time()
        response: Response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response


class SecurityMiddleWare(MiddleWare, InjectableMiddlewareInterface):

    def __init__(self, app, dispatch=None) -> None:
        MiddleWare.__init__(self, app, dispatch)
        InjectableMiddlewareInterface.__init__(self)

    async def dispatch(self, request: Request, call_next: Callable[..., Response]):
        response: Response = await call_next(request)
        return response

    @InjectInMethod
    def inject_middleware(self, securityService: SecurityService):
        self.securityService = securityService
