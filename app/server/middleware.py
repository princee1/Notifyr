from fastapi.responses import JSONResponse
from utils.constant import ConfigAppConstant
from services.config_service import ConfigService
from classes.permission import AuthPermission
from services.security_service import SecurityService, JWTAuthService
from container import InjectInMethod
from fastapi import HTTPException, Request, Response, FastAPI, status
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction
from typing import Any, Awaitable, Callable, MutableMapping
import time
from interface.injectable_middleware import InjectableMiddlewareInterface
from utils.dependencies import get_api_key, get_client_ip, get_bearer_token_from_request
from cryptography.fernet import InvalidToken
from enum import Enum


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
        current_time = time.time()
        if current_time - self.configService.config_json_app.data[ConfigAppConstant.META_KEY][ConfigAppConstant.EXPIRATION_TIMESTAMP_KEY] < 0:
            return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "Unauthorized", "detail": "All Access and Auth token are expired"})
        try:
            request_api_key = get_api_key(request)
            if request_api_key is None:
                return Response(status_code=status.HTTP_401_UNAUTHORIZED, content="Unauthorized")
            client_ip = get_client_ip(request)
            if not self.securityService.verify_server_access(request_api_key, client_ip):
                return Response(status_code=status.HTTP_401_UNAUTHORIZED, content="Unauthorized")
            response: Response = await call_next(request)
            return response
        except InvalidToken:
            return Response(status_code=status.HTTP_401_UNAUTHORIZED, content='Unauthorized')

    @InjectInMethod
    def inject_middleware(self, securityService: SecurityService, configService: ConfigService):
        self.securityService = securityService
        self.configService = configService


class AnalyticsMiddleware(MiddleWare, InjectableMiddlewareInterface):
    ...


class JWTAuthMiddleware(MiddleWare, InjectableMiddlewareInterface):
    def __init__(self, app, dispatch=None) -> None:
        MiddleWare.__init__(self, app, dispatch)
        InjectableMiddlewareInterface.__init__(self)

    @InjectInMethod
    def inject_middleware(self, jwtService: JWTAuthService):
        self.jwtService = jwtService

    async def dispatch(self,  request: Request, call_next: Callable[..., Response]):
        token = get_bearer_token_from_request(request)
        client_ip = get_client_ip(request)
        authPermission: AuthPermission = self.jwtService.verify_permission(
            token, client_ip)
        request.state.authPermission = authPermission
        return await call_next(request)


class MiddlewarePriority(Enum):

    PROCESS_TIME = 1
    ANALYTICS = 2
    SECURITY = 3
    AUTH = 4
