from fastapi import Depends, Query,status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.container import InjectInMethod
from  app.definition._ressource import BaseHTTPRessource,HTTPRessource, IncludeWebsocket, PingService, UseHandler, UsePermission, UseRoles
from app.services.celery_service import CeleryService
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.security_service import JWTAuthService
from app.websockets.chat_ws import ChatWebSocket
from app.decorators.handlers import ServiceAvailabilityHandler, WebSocketHandler
from app.classes.auth_permission import WSPermission,Role
from app.decorators.permissions import JWTRouteHTTPPermission
from app.utils.dependencies import get_auth_permission
from app.utils.helper import generateId


CHAT_PREFIX= 'chat'

class SupportModel(BaseModel):
    ...

SUPPORT_PREFIX = 'support'


@UseRoles([Role.CHAT])
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(prefix=SUPPORT_PREFIX,websockets=[ChatWebSocket])
class SupportRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self,jwtAuthService:JWTAuthService, configService: ConfigService,contactService:ContactsService,celeryService:CeleryService):
        super().__init__()
        self.contactService = contactService
        self.configService = configService
        self.celeryService = celeryService
        self.jwtAuthService = jwtAuthService

    @BaseHTTPRessource.Post('/')
    def support(self,supportModel:SupportModel, register:bool = Query(False),chat_upgrade:bool = Query(False),authPermission=Depends(get_auth_permission)):
        ...
    
    @PingService([JWTAuthService])
    @UseHandler(WebSocketHandler)
    @BaseHTTPRessource.Get('/live-chat-permission/{ws_path}',)
    def issue_chat_permission(self, ws_path:str, authPermission=Depends(get_auth_permission)):

        self._check_ws_path(ws_path)
        run_id = self.websockets[ChatWebSocket.__name__].run_id
        token = self.jwtAuthService.encode_ws_token(run_id,ws_path,self.configService.CHAT_EXPIRATION)
        return JSONResponse(status_code=status.HTTP_201_CREATED,content={
            'chat-token':token,
        })


