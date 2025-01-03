from services.security_service import SecurityService
from container import InjectInMethod
from fastapi import HTTPException, Request, Response, FastAPI,status
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction
from typing import Any, Awaitable, Callable, MutableMapping
import time
from interface.injectable_middleware import InjectableMiddlewareInterface
from .dependencies import get_api_key, get_client_ip

MIDDLEWARE: dict[str, type] = {}

class MiddleWare(BaseHTTPMiddleware):

    def __init_subclass__(cls: type) -> None:
        MIDDLEWARE[cls.__name__] = cls

class ProcessTimeMiddleWare(MiddleWare):

    def __init__(self, app, dispatch=None) -> None:
        super().__init__(app, dispatch)

    async def dispatch(self, request: Request, call_next: Callable[..., Response]):
        start_time = time.time()
        response: Response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time) + ' (s)'
        return response

class SecurityMiddleWare(MiddleWare, InjectableMiddlewareInterface):

    def __init__(self, app, dispatch=None) -> None:
        MiddleWare.__init__(self, app, dispatch)
        InjectableMiddlewareInterface.__init__(self)

    async def dispatch(self, request: Request, call_next: Callable[..., Response]):
        request_api_key = get_api_key(request)
        if request_api_key is None:
            return Response(status_code=status.HTTP_401_UNAUTHORIZED, content="Unauthorized")
        client_ip = get_client_ip(request)
        if not self.securityService.verify_server_access(request_api_key,client_ip):
            return Response(status_code=status.HTTP_401_UNAUTHORIZED, content="Unauthorized")
        response: Response = await call_next(request)
        return response

    @InjectInMethod
    def inject_middleware(self, securityService: SecurityService):
        self.securityService = securityService

class AnalyticsMiddleware(MiddleWare,InjectableMiddlewareInterface):
    ...