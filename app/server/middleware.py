from uuid import uuid4
from fastapi.responses import JSONResponse
from app.classes.auth_permission import AuthPermission, ClientAccessInfo, ClientType, filter_asset_permission, parse_authPermission_enum
from app.definition._middleware import  ApplyOn, BypassOn, ExcludeOn, MiddleWare, MiddlewarePriority,MIDDLEWARE
from app.depends.orm_cache import BlacklistClientCache, BlacklistGroupCache
from app.errors.security_error import SecurityIdentityNotResolvedError
from app.errors.service_error import MiniServiceDoesNotExistsError
from app.services.admin_service import AdminService
from app.services.database.redis_service import RedisService
from app.services.monitoring_service import MonitoringService
from app.services.config_service import ConfigService, WorkerService
from app.services.security_service import SecurityService, JWTAuthService
from app.container import Get, InjectInMethod
from fastapi import HTTPException, Request, Response,status
from slowapi.middleware import SlowAPIMiddleware
from typing import Callable
import time
from app.utils.constant import HTTPHeaderConstant, MonitorConstant
from app.depends.dependencies import get_client_ip,get_bearer_token_from_request
    
configService = Get(ConfigService)

class MetaDataMiddleWare(MiddleWare):
    priority = MiddlewarePriority.METADATA
    def __init__(self, app, dispatch=None) -> None:
        super().__init__(app, dispatch)
        self.configService:ConfigService = Get(ConfigService)
        self.monitoringService = Get(MonitoringService)
        self.workerService= Get(WorkerService)

    @ExcludeOn(['/docs/*','/openapi.json'])
    async def dispatch(self, request: Request, call_next: Callable[..., Response]):
        start_time = time.time()
        self.monitoringService.gauge_inc(MonitorConstant.CONNECTION_COUNT)
        self.monitoringService.counter_inc(MonitorConstant.CONNECTION_TOTAL)
        request_id = str(uuid4())
        request.state.request_id =request_id

        try:
            response: Response = await call_next(request)
            process_time = time.time() - start_time
            
            response.headers[HTTPHeaderConstant.X_PROCESS_TIME] = f"{process_time * 1000:.1f} (ms)"
            response.headers[HTTPHeaderConstant.X_INSTANCE_ID]= self.workerService.INSTANCE_ID
            response.headers[HTTPHeaderConstant.X_REQUEST_ID] = request_id

            self.monitoringService.histogram_observe(MonitorConstant.REQUEST_LATENCY,process_time)
            return response
        except HTTPException as e:
            process_time = time.time() - start_time
            self.monitoringService.histogram_observe(MonitorConstant.REQUEST_LATENCY,process_time)
            return JSONResponse (e.detail,e.status_code,{"X-Error-Time":str(process_time) + ' (s)',HTTPHeaderConstant.X_INSTANCE_ID:self.workerService.INSTANCE_ID})
        finally:
            self.monitoringService.gauge_dec(MonitorConstant.CONNECTION_COUNT)

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
        self.redisService: RedisService = Get(RedisService)

    @BypassOn(not configService.SECURITY_FLAG)
    @ExcludeOn(['/','/contacts/manage/*'])
    @ExcludeOn(['/docs/*','/openapi.json'])
    @ExcludeOn(['/link/visits/*','/link/email-track/*'])
    @ExcludeOn(['/auth/login/','/auth/revoke/','/auth/refresh/'])
    async def dispatch(self,  request: Request, call_next: Callable[..., Response]):
        try:  
            token = get_bearer_token_from_request(request)
            async with self.jwtService.lock('reader'):
                clientInfo: ClientAccessInfo = self.jwtService.verify_client_token_permission(token)

            client_id = clientInfo.get('client_id',None)

            if not client_id:
                raise SecurityIdentityNotResolvedError(None,'Cannot identify the client since the client_id is not provided')

            async with self.adminService.lock('reader',client_id) as clientService:
                clientInfo['client_type'] = clientService.client.client_type
                clientInfo['auth_type'] = clientService.client.auth_type
                
                client_ip = get_client_ip(request) #TODO : check wether we must use the scope to verify the client
                
                clientService.verify_client_origin(client_ip)
                clientService.compare_auth_signature(clientInfo['auth_signature'])

                if not clientService.client.authenticated:
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Client is not authenticated")
                
                if clientService.client.client_type != ClientType.Admin: 
                    async with self.redisService.redis_security.pipeline() as pipe:
                        if clientService.group_id:
                            await BlacklistGroupCache.Get([clientService.group_id],redis=pipe) # group 
                        await BlacklistClientCache.Get([client_id,''],redis=pipe) # client
                        await BlacklistClientCache.Get([client_id,token],redis=pipe) # token
                        flags = await pipe.execute()

                    if any(flags):
                        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"message": "Client is blacklisted","flags":flags})
                       
                request.state.clientInfo = clientInfo
                request.state.authPermission = clientService.authPermission

        except HTTPException as e:
            return JSONResponse(e.detail,e.status_code,e.headers)

        except MiniServiceDoesNotExistsError as e:
            return JSONResponse(status_code= status.HTTP_401_UNAUTHORIZED)
        
        except SecurityIdentityNotResolvedError as e:
            return JSONResponse({'message':e.reason},status_code= status.HTTP_401_UNAUTHORIZED)

        return await call_next(request)
class CustomSlowApiMiddleware(SlowAPIMiddleware):
    priority = MiddlewarePriority.LIMITER

MIDDLEWARE[CustomSlowApiMiddleware.__name__] = CustomSlowApiMiddleware
