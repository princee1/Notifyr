import asyncio
from fastapi.responses import JSONResponse
from app.classes.auth_permission import AuthPermission, ClientType, Role, Scope, parse_authPermission_enum
from app.definition._middleware import  ApplyOn, BypassOn, ExcludeOn, MiddleWare, MiddlewarePriority,MIDDLEWARE
from app.depends.orm_cache import BlacklistORMCache, ChallengeORMCache, ClientORMCache
from app.models.security_model import BlacklistORM, ChallengeORM, ClientORM
from app.services.admin_service import AdminService
from app.services.celery_service import TaskService
from app.services.config_service import ConfigService
from app.services.security_service import SecurityService, JWTAuthService
from app.container import Get, InjectInMethod
from fastapi import HTTPException, Request, Response, FastAPI,status
from typing import Any, Awaitable, Callable, MutableMapping
import time
from app.utils.constant import ConfigAppConstant, HTTPHeaderConstant
from app.depends.dependencies import get_api_key, get_auth_permission, get_client_from_request, get_client_ip,get_bearer_token_from_request, get_response_id
from cryptography.fernet import InvalidToken
from app.depends.variables import SECURITY_FLAG
from app.utils.helper import generateId
from app.depends.funcs_dep import GetClient
from starlette.background import BackgroundTask


        
class MetaDataMiddleWare(MiddleWare):
    priority = MiddlewarePriority.METADATA
    def __init__(self, app, dispatch=None) -> None:
        super().__init__(app, dispatch)
        self.taskService:TaskService = Get(TaskService)
        self.configService:ConfigService = Get(ConfigService)

        self.instance_id = str(self.configService.INSTANCE_ID)
        self.process_pid = self.configService.PROCESS_PID
        self.parent_pid = self.configService.PARENT_PID


    @ExcludeOn(['/docs/*','/openapi.json'])
    async def dispatch(self, request: Request, call_next: Callable[..., Response]):
        start_time = time.time()
        self.taskService.connection_count.inc()
        self.taskService.connection_total.inc()

        try:
            response: Response = await call_next(request)
            process_time = time.time() - start_time
            
            response.headers[HTTPHeaderConstant.X_PROCESS_TIME] = f"{process_time * 1000:.1f} (ms)"
            response.headers[HTTPHeaderConstant.X_INSTANCE_ID]= self.instance_id
            response.headers[HTTPHeaderConstant.X_PROCESS_PID] =self.process_pid
            response.headers[HTTPHeaderConstant.X_PARENT_PROCESS_PID] = self.parent_pid

            self.taskService.request_latency.observe(process_time)
            return response
        except HTTPException as e:
            process_time = time.time() - start_time
            self.taskService.request_latency.observe(process_time)
            return JSONResponse (e.detail,e.status_code,{"X-Error-Time":str(process_time) + ' (s)','X-Instance-Id':self.instance_id})
        finally:
            self.taskService.connection_count.dec()

class LoadBalancerMiddleWare(MiddleWare):
    def __init__(self, app, dispatch = None):
        super().__init__(app, dispatch)
        self.configService: ConfigService = Get(ConfigService)
        self.securityService: SecurityService = Get(SecurityService)
    
    @ExcludeOn(['/docs/*','/openapi.json'])
    async def dispatch(self, request:Request, call_next:Callable[...,Response]):
        response = await call_next(request)
        # TODO add headers like application id, notifyr-service id, Signature-Service, myb generation id 
        return response

class SecurityMiddleWare(MiddleWare):
    priority = MiddlewarePriority.SECURITY
    def __init__(self,app, dispatch=None) -> None:
        super().__init__(app, dispatch)
        self.securityService = Get(SecurityService)
        self.configService = Get(ConfigService)

    @BypassOn()
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
        self.configService: ConfigService = Get(ConfigService)
        self.adminService: AdminService = Get(AdminService)

    @BypassOn(not SECURITY_FLAG)
    @ExcludeOn(['/auth/generate/*','/contacts/manage/*'])
    @ExcludeOn(['/link/visits/*','/link/email-track/*'])
    @ExcludeOn(['/docs/*','/openapi.json'])
    @ExcludeOn(['/'])
    async def dispatch(self,  request: Request, call_next: Callable[..., Response]):
        try:  
            token = get_bearer_token_from_request(request)
            client_ip = get_client_ip(request) #TODO : check wether we must use the scope to verify the client
            authPermission: AuthPermission = self.jwtService.verify_auth_permission(token, client_ip)
          
            client_id = authPermission['client_id']
            group_id = authPermission['group_id']

            client:ClientORM = await ClientORMCache.Cache([group_id,client_id],client_id=client_id,cid="id",authPermission=authPermission)

            #TODO check group id
            if not client.authenticated:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Client is not authenticated")

            if client.client_type != ClientType.Admin: 
                is_blacklisted:bool = await BlacklistORMCache.Cache([group_id,client_id],client)

                if is_blacklisted :
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Client is blacklisted")

            request.state.client = client
            parse_authPermission_enum(authPermission)
            request.state.authPermission = authPermission
        except HTTPException as e:
            return JSONResponse(e.detail,e.status_code,e.headers)

        return await call_next(request)

    
class BackgroundTaskMiddleware(MiddleWare):
    priority = MiddlewarePriority.BACKGROUND_TASK_SERVICE
    def __init__(self, app, dispatch = None):
        super().__init__(app, dispatch)
        self.taskService:TaskService = Get(TaskService)
    
    @ExcludeOn(['/docs/*','/openapi.json'])
    @ExcludeOn(['/'])
    async def dispatch(self, request:Request, call_next):
        request_id = generateId(25)
        request.state.request_id = request_id
        response:Response = await call_next(request)
        rq_response_id = get_response_id(response) 
        if rq_response_id in self.taskService.sharing_task:
            if len(self.taskService.sharing_task[rq_response_id].taskConfig)>0:
                async def callback():
                    await asyncio.sleep(0.1)
                    return await self.taskService(rq_response_id)
                response.background= BackgroundTask(callback)
        else: 
            self.taskService._delete_tasks(request_id) #NOTE if theres no rq_response_id in the response this means we can safely remove the reference
        return response   
        
class UserAppMiddleware(MiddleWare):
    priority = MiddlewarePriority.USER_APP

    def __init__(self, app, dispatch = None):
        super().__init__(app, dispatch)
        self.adminService = Get(AdminService)
        self.jwtAuthService = Get(JWTAuthService)
        self.configService = Get(ConfigService)
        self.securityService = Get(SecurityService)

    @ExcludeOn(['/docs/*','/openapi.json','/contacts/manage/*'])
    @ApplyOn(['/auth/generate/admin/*'])
    @ExcludeOn(['/link/visits/*','/link/email-track/*'])
    @ExcludeOn(['/'])
    async def dispatch(self, request:Request, call_next:Callable[[Request],Response]):
        return await super().dispatch(request, call_next)


class ChallengeMatchMiddleware(MiddleWare):
    priority = MiddlewarePriority.CHALLENGE

    @BypassOn(not SECURITY_FLAG)
    @ExcludeOn(['/docs/*','/openapi.json','/contacts/manage/*'])
    @ExcludeOn(['/auth/generate/*','/auth/refresh/*'])
    @ExcludeOn(['/link/visits/*','/link/email-track/*'])
    @ExcludeOn(['/'])
    async def dispatch(self, request:Request, call_next:Callable[[Request],Response]):
        authPermission: AuthPermission = await get_auth_permission(request)
        client:ClientORM = await get_client_from_request(request)
        challenge = authPermission['challenge']

        db_challenge:ChallengeORM = await ChallengeORMCache.Cache(client.client_id,client) 

        if challenge != db_challenge.challenge_auth:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Challenge does not match") 
        
        return await call_next(request)
