from typing import Annotated
from fastapi import Depends, Request,status
from fastapi.responses import JSONResponse
from app.container import Get, InjectInMethod
from app.decorators.handlers import CeleryTaskHandler, ServiceAvailabilityHandler, WebSocketHandler
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, PingService, UseHandler, UseLimiter, UsePermission, UsePipe, UseRoles
from app.services.task_service import TaskService, CeleryService
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.security_service import JWTAuthService
from app.depends.dependencies import get_auth_permission
from app.classes.auth_permission import AuthPermission, MustHave, Role
from app.websockets.redis_backend_ws  import RedisBackendWebSocket
from pydantic.fields import Field


REDIS_EXPIRATION = 360000
REDIS_PREFIX = 'redis'

CELERY_PREFIX= 'celery'

BACKGROUND_PREFIX  = 'background'

@UseRoles([Role.REDIS])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler)
@PingService([CeleryService])
@HTTPRessource(prefix=CELERY_PREFIX)
class CeleryRessource(BaseHTTPRessource):
    
    @InjectInMethod
    def __init__(self,celeryService:CeleryService,configService:ConfigService,jwtService:JWTAuthService):
        super().__init__(None,None)
        self.celeryService:CeleryService = celeryService
        self.configService:ConfigService = configService
        self.jwtAuthService: JWTAuthService = jwtService

    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Get('/task/{task_id}')
    def check_task(self,task_id:str,authPermission=Depends(get_auth_permission)):
        return self.celeryService.seek_result(task_id)

    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Delete('/task/{task_id}')
    def cancel_task(self,task_id:str,authPermission=Depends(get_auth_permission)):
        return self.celeryService.cancel_task(task_id)

    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Get('/schedule/{schedule_id}')
    def check_schedule(self,schedule_id:str,authPermission=Depends(get_auth_permission)):
        return self.celeryService.seek_schedule(schedule_id)
        

    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Delete('/schedule/{schedule_id}')
    def delete_schedule(self,schedule_id:str,authPermission=Depends(get_auth_permission)):
       return  self.celeryService.delete_schedule(schedule_id)
        
    @PingService([JWTAuthService])
    @UseHandler(WebSocketHandler)
    @BaseHTTPRessource.Get('/create-permission/{ws_path}',)
    def invoke_notify_permission(self, ws_path:str, authPermission=Depends(get_auth_permission)):
        self._check_ws_path(ws_path)

        redis_run_id = self.websockets[RedisBackendWebSocket.__name__].run_id
        token = self.jwtAuthService.encode_ws_token(redis_run_id,REDIS_EXPIRATION)
        return JSONResponse(status_code=status.HTTP_201_CREATED,content={
            'redis-token':token,
        })
    
    @UseRoles([Role.ADMIN],options=[MustHave(Role.ADMIN)])
    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Delete('/purge/{queue}/{task_id}',mount=False)
    def purge_celery_task(self,queue:str, task_id:str, authPermission:AuthPermission = Depends(get_auth_permission)):
        """
        Purge a specific task from the celery queue.
        """
        return self.celeryService.purge(queue_name=queue, task_id=task_id)
    


@UseHandler(ServiceAvailabilityHandler)
@UsePermission(JWTRouteHTTPPermission)
@PingService([RedisService])
@HTTPRessource(prefix=BACKGROUND_PREFIX)
class BackgroundTaskRessource(BaseHTTPRessource):
    
    def __init__(self,redisService:RedisService,configService:ConfigService,taskService:TaskService):
        self.redisService = redisService
        self.configService = configService
        self.backgroundTask = taskService
    
    @UseLimiter(limit_value='10/day')
    @BaseHTTPRessource.Get('/{task_id}')
    def get_result(self,task_id:str,authPermission=Depends(get_auth_permission)):
        ...
    

@HTTPRessource(prefix=REDIS_PREFIX, routers=[CeleryRessource,],websockets=[RedisBackendWebSocket])
class RedisBackendRessource(BaseHTTPRessource):
    
    @UseHandler(ServiceAvailabilityHandler)
    @UsePermission(JWTRouteHTTPPermission)
    @UseLimiter(limit_value='10/day')
    @BaseHTTPRessource.Get('/')
    def get(self,request:Request,authPermission=Depends(get_auth_permission)):
        return 
    


