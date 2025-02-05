from typing import Annotated
from fastapi import Depends,status
from fastapi.responses import JSONResponse
from app.container import Get, InjectInMethod
from app.decorators.handlers import CeleryTaskHandler, ServiceAvailabilityHandler, WebSocketHandler
from app.decorators.permissions import JWTRouteHTTPPermission
from app.decorators.pipes import CeleryTaskIdentifierPipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UseHandler, UsePermission, UsePipe, UseRoles
from app.services.celery_service import CeleryService
from app.services.config_service import ConfigService
from app.services.security_service import JWTAuthService
from app.utils.dependencies import get_auth_permission
from app.classes.auth_permission import MustHave, Role
from app.websockets.redis_backend_ws  import RedisBackendWebSocket
from pydantic.fields import Field


REDIS_EXPIRATION = 360000
REDIS_PREFIX = 'redis'

@UseRoles([Role.REDIS])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler)
@HTTPRessource(prefix=REDIS_PREFIX,websockets=[RedisBackendWebSocket])
class RedisBackendRessource(BaseHTTPRessource):
    
    @InjectInMethod
    def __init__(self,celeryService:CeleryService,configService:ConfigService,jwtService:JWTAuthService):
        super().__init__(None,None)
        self.celeryService:CeleryService = celeryService
        self.configService:ConfigService = configService
        self.jwtAuthService: JWTAuthService = jwtService
        self.run_id = '1'

    @UseHandler(CeleryTaskHandler)
    @UsePipe(CeleryTaskIdentifierPipe)
    @BaseHTTPRessource.Get('/result/{task_id}')
    def check_status(self,task_id:str,authPermission=Depends(get_auth_permission)):
        self.celeryService.pingService()
        return task_id

    #@UseRoles(options=[MustHave(Role.ADMIN)])
    @BaseHTTPRessource.Get('/schedule/{schedule_id}')
    def check_schedule(self,schedule_id:str,authPermission=Depends(get_auth_permission)):
        ...

    @UseRoles(options=[MustHave(Role.ADMIN)])
    @BaseHTTPRessource.Delete('/schedule/{schedule_id}')
    def delete_schedule(self,schedule_id:str,authPermission=Depends(get_auth_permission)):
        ...

    @UseHandler(WebSocketHandler)
    @BaseHTTPRessource.Get('/create-permission/{ws_path}',)
    def invoke_chat_permission(self, ws_path:str, authPermission=Depends(get_auth_permission)):
        self.celeryService.pingService()
        self.jwtAuthService.pingService()
        self._check_ws_path(ws_path)

        token = self.jwtAuthService.encode_ws_token(self.run_id,ws_path,REDIS_EXPIRATION)
        return JSONResponse(status_code=status.HTTP_201_CREATED,content={
            'chat-token':token,
        })


    


