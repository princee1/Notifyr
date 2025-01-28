from fastapi.responses import JSONResponse
from app.classes.auth_permission import AuthPermission, Role
from app.services.config_service import ConfigService
from app.services.security_service import SecurityService, JWTAuthService
from app.container import InjectInMethod
from fastapi import HTTPException, Request, Response, FastAPI,status
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction
from typing import Any, Awaitable, Callable, MutableMapping
import time
from app.interface.injectable_middleware import InjectableMiddlewareInterface
from app.utils.constant import ConfigAppConstant
from app.utils.dependencies import get_api_key, get_client_ip,get_bearer_token_from_request
from cryptography.fernet import InvalidToken
from enum import Enum


MIDDLEWARE: dict[str, type] = {}
class MiddlewarePriority(Enum):

    PROCESS_TIME = 1
    ANALYTICS = 2
    SECURITY = 3
    AUTH = 4


class MiddleWare(BaseHTTPMiddleware):

    def __init_subclass__(cls: type) -> None:
        MIDDLEWARE[cls.__name__] = cls
        setattr(cls,'priority',None)
        
class ProcessTimeMiddleWare(MiddleWare):

    def __init__(self, app, dispatch=None) -> None:
        super().__init__(app, dispatch)

    async def dispatch(self, request: Request, call_next: Callable[..., Response]):
        start_time = time.time()
        response: Response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time) + ' (s)'
        return response

ProcessTimeMiddleWare.priority = MiddlewarePriority.PROCESS_TIME


class SecurityMiddleWare(MiddleWare, InjectableMiddlewareInterface):

    def __init__(self, app, dispatch=None) -> None:
        MiddleWare.__init__(self, app, dispatch)
        InjectableMiddlewareInterface.__init__(self)

    async def dispatch(self, request: Request, call_next: Callable[..., Response]):
        current_time = time.time()
        timestamp =  self.configService.config_json_app.data[ConfigAppConstant.META_KEY][ConfigAppConstant.EXPIRATION_TIMESTAMP_KEY]
        diff = timestamp -current_time
        if diff< 0:
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

SecurityMiddleWare.priority = MiddlewarePriority.SECURITY


class AnalyticsMiddleware(MiddleWare, InjectableMiddlewareInterface):
    async def dispatch(self, request, call_next):
        return await call_next(request)

AnalyticsMiddleware.priority = MiddlewarePriority.ANALYTICS

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
        try:
            authPermission: AuthPermission = self.jwtService.verify_permission(
                token, client_ip)
            authPermission["roles"] = [Role._member_map_[r] for r in authPermission["roles"]]
            request.state.authPermission = authPermission
            return await call_next(request)
        except HTTPException as e:
            return JSONResponse(e.detail,e.status_code)
        except Exception as e:
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,content={'message':''})

JWTAuthMiddleware.priority = MiddlewarePriority.AUTH
