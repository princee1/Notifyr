from typing import Annotated
from fastapi import Depends,status
from fastapi.responses import JSONResponse
from app.container import Get, InjectInMethod
from app.decorators.handlers import CeleryTaskHandler, ServiceAvailabilityHandler, WebSocketHandler
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, PingService, UseHandler, UsePermission, UsePipe, UseRoles
from app.services.celery_service import CeleryService
from app.services.config_service import ConfigService
from app.services.security_service import JWTAuthService
from app.utils.dependencies import get_auth_permission
from app.classes.auth_permission import AuthPermission, MustHave, Role
from app.websockets.redis_backend_ws  import RedisBackendWebSocket
from pydantic.fields import Field


REDIS_EXPIRATION = 360000
REDIS_PREFIX = 'redis'

@UseRoles([Role.REDIS])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler)
@PingService([CeleryService])
@HTTPRessource(prefix=REDIS_PREFIX,websockets=[RedisBackendWebSocket])
class RedisBackendRessource(BaseHTTPRessource):
    
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
        self.celeryService.cancel_task(task_id)

    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Get('/schedule/{schedule_id}')
    def check_schedule(self,schedule_id:str,authPermission=Depends(get_auth_permission)):
        return self.celeryService.seek_schedule(schedule_id)
        

    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Delete('/schedule/{schedule_id}')
    def delete_schedule(self,schedule_id:str,authPermission=Depends(get_auth_permission)):
        self.celeryService.delete_schedule(schedule_id)
        
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


    


