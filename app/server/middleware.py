import asyncio
from fastapi.responses import JSONResponse
from app.classes.auth_permission import AuthPermission, Role
from app.services.celery_service import BackgroundTaskService
from app.services.config_service import ConfigService
from app.services.security_service import SecurityService, JWTAuthService
from app.container import Get, InjectInMethod
from fastapi import HTTPException, Request, Response, FastAPI,status
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction
from starlette.datastructures import MutableHeaders,Headers
from typing import Any, Awaitable, Callable, MutableMapping
import time
from app.utils.constant import ConfigAppConstant, HTTPHeaderConstant
from app.utils.dependencies import get_api_key, get_client_ip,get_bearer_token_from_request, get_response_id
from cryptography.fernet import InvalidToken
from enum import Enum

from app.utils.helper import generateId


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
        
class ProcessTimeMiddleWare(MiddleWare):
    priority = MiddlewarePriority.PROCESS_TIME
    def __init__(self, app, dispatch=None) -> None:
        super().__init__(app, dispatch)

    async def dispatch(self, request: Request, call_next: Callable[..., Response]):
        start_time = time.time()
        response: Response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time) + ' (s)'
        return response

class SecurityMiddleWare(MiddleWare):
    priority = MiddlewarePriority.SECURITY
    def __init__(self,app, dispatch=None) -> None:
        super().__init__(app, dispatch)
        self.securityService = Get(SecurityService)
        self.configService = Get(ConfigService)



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
       
class AnalyticsMiddleware(MiddleWare):
    priority = MiddlewarePriority.ANALYTICS
    async def dispatch(self, request, call_next):
        return await call_next(request)

class JWTAuthMiddleware(MiddleWare):
    priority = MiddlewarePriority.AUTH
    def __init__(self, app, dispatch=None) -> None:
        super().__init__(app, dispatch)
        self.jwtService:JWTAuthService = Get(JWTAuthService)

    async def dispatch(self,  request: Request, call_next: Callable[..., Response]):
        try:  
            token = get_bearer_token_from_request(request)
            client_ip = get_client_ip(request) #TODO : check wether we must use the scope to verify the client
            authPermission: AuthPermission = self.jwtService.verify_permission(token, client_ip)
            authPermission["roles"] = [Role._member_map_[r] for r in authPermission["roles"]]
            request.state.authPermission = authPermission
        except HTTPException as e:
            return JSONResponse(e.detail,e.status_code,e.headers)

        return await call_next(request)
        

class BackgroundTaskMiddleware(MiddleWare):
    priority = MiddlewarePriority.BACKGROUND_TASK_SERVICE
    def __init__(self, app, dispatch = None):
        super().__init__(app, dispatch)
        self.backgroundTaskService:BackgroundTaskService = Get(BackgroundTaskService)
    
    async def dispatch(self, request:Request, call_next):
        request_id = generateId(25)
        self.backgroundTaskService._register_tasks(request_id)
        request.state.request_id = request_id
        response = await call_next(request)
        rq_response_id = get_response_id(response) #NOTE if theres no rq_response_id in the response this means we can safely remove the referencece
        if rq_response_id:
            asyncio.create_task(self.backgroundTaskService(rq_response_id)) 
        else: 
            self.backgroundTaskService._delete_tasks(request_id)
        return response   
        
