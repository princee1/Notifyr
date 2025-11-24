from uuid import uuid4
from fastapi.responses import JSONResponse
from app.classes.auth_permission import AuthPermission, ClientType, parse_authPermission_enum
from app.definition._middleware import  ApplyOn, BypassOn, ExcludeOn, MiddleWare, MiddlewarePriority,MIDDLEWARE
from app.depends.orm_cache import AuthPermissionCache, BlacklistORMCache, ChallengeORMCache, ClientORMCache
from app.models.security_model import BlacklistORM, ChallengeORM, ClientORM
from app.services.admin_service import AdminService
from app.services.task_service import TaskService
from app.services.config_service import ConfigService
from app.services.security_service import SecurityService, JWTAuthService
from app.container import Get, InjectInMethod
from fastapi import HTTPException, Request, Response,status
from typing import Callable
import time
from app.utils.constant import HTTPHeaderConstant
from app.depends.dependencies import get_auth_permission, get_client_from_request, get_client_ip,get_bearer_token_from_request, get_response_id
from app.utils.globals import PARENT_PID, PROCESS_PID
    

configService = Get(ConfigService)

class MetaDataMiddleWare(MiddleWare):
    priority = MiddlewarePriority.METADATA
    def __init__(self, app, dispatch=None) -> None:
        super().__init__(app, dispatch)
        self.taskService:TaskService = Get(TaskService)
        self.configService:ConfigService = Get(ConfigService)

        self.instance_id = str(self.configService.INSTANCE_ID)
        self.process_pid = PROCESS_PID
        self.parent_pid = PARENT_PID


    @ExcludeOn(['/docs/*','/openapi.json'])
    async def dispatch(self, request: Request, call_next: Callable[..., Response]):
        start_time = time.time()
        self.taskService.connection_count.inc()
        self.taskService.connection_total.inc()
        request.state.request_id = str(uuid4())

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
    priority = MiddlewarePriority.LOAD_BALANCER

    def __init__(self, app, dispatch = None):
        super().__init__(app, dispatch)
        self.configService: ConfigService = Get(ConfigService)
        self.securityService: SecurityService = Get(SecurityService)
    
    @ExcludeOn(['/docs/*','/openapi.json'])
    async def dispatch(self, request:Request, call_next:Callable[...,Response]):
        response = await call_next(request)
        # TODO add headers like application id, notifyr-service id, Signature-Service, myb generation id 
        return response
                 
class JWTAuthMiddleware(MiddleWare):
    priority = MiddlewarePriority.AUTH
    def __init__(self, app, dispatch=None) -> None:
        super().__init__(app, dispatch)
        self.jwtService:JWTAuthService = Get(JWTAuthService)
        self.configService: ConfigService = Get(ConfigService)
        self.adminService: AdminService = Get(AdminService)


    def _copy_client_into_auth(self,client:ClientORM,permission:AuthPermission):
        permission['client_type'] = client.client_type
        permission['scope'] = client.client_scope
        permission['issued_for'] = client.issued_for
        permission['auth_type'] = client.auth_type
        permission['client_username'] = client.client_username

        

    @BypassOn(not configService.SECURITY_FLAG)
    @ExcludeOn(['/auth/generate/*','/contacts/manage/*'])
    @ExcludeOn(['/link/visits/*','/link/email-track/*'])
    @ExcludeOn(['/docs/*','/openapi.json'])
    @ExcludeOn(['/'])
    async def dispatch(self,  request: Request, call_next: Callable[..., Response]):
        try:  
            token = get_bearer_token_from_request(request)
            client_ip = get_client_ip(request) #TODO : check wether we must use the scope to verify the client
            origin = ...

            authPermission: AuthPermission = self.jwtService.verify_auth_permission(token, client_ip)
          
            client_id = authPermission['client_id']
            group_id = authPermission['group_id']

            client:ClientORM = await ClientORMCache.Cache([group_id,client_id],client_id=client_id,cid="id",authPermission=authPermission)

            self._copy_client_into_auth(client,authPermission)
            self.jwtService.verify_client_origin(authPermission,client_ip,origin)

            #TODO check group id
            if not client.authenticated:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client is not authenticated")

            if client.client_type != ClientType.Admin: 

                if await BlacklistORMCache.Cache([group_id,client_id],client):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Client is blacklisted")

            request.state.client = client

            policies = await AuthPermissionCache.Cache([group_id,client_id],client)
            authPermission= AuthPermission(**{**authPermission,**policies})

            parse_authPermission_enum(authPermission)
            request.state.authPermission = authPermission

        except HTTPException as e:
            return JSONResponse(e.detail,e.status_code,e.headers)

        return await call_next(request)
         
class ChallengeMatchMiddleware(MiddleWare):
    priority = MiddlewarePriority.CHALLENGE

    @BypassOn(not configService.SECURITY_FLAG)
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
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Challenge does not match") 
        
        return await call_next(request)
