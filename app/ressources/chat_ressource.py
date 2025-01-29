from fastapi import Depends,status
from fastapi.responses import JSONResponse
from app.container import InjectInMethod
from  app.definition._ressource import BaseHTTPRessource,HTTPRessource, IncludeWebsocket, UseHandler, UsePermission, UseRoles
from app.services.config_service import ConfigService
from app.services.security_service import JWTAuthService
from app.websockets.chat_ws import ChatWebSocket
from app.decorators.handlers import ServiceAvailabilityHandler, WebSocketHandler
from app.classes.auth_permission import WSPermission,Role
from app.decorators.permissions import JWTRouteHTTPPermission
from app.utils.dependencies import get_auth_permission


CHAT_PREFIX= 'chat'

#@IncludeWebsocket(ChatWebSocket)
@UseRoles([Role.CHAT])
@UseHandler(ServiceAvailabilityHandler)
@HTTPRessource(prefix=CHAT_PREFIX,websockets=[ChatWebSocket])
class LiveChatRessource(BaseHTTPRessource):
    
    @InjectInMethod
    def __init__(self,jwtAuthService:JWTAuthService,configService:ConfigService):
        super().__init__()
        self.jwtAuthService = jwtAuthService
        self.configService = configService

    @UsePermission(JWTRouteHTTPPermission)
    @UseHandler(WebSocketHandler)
    @BaseHTTPRessource.Get('/invoke-permission/{ws_path}',)
    def invoke_chat_permission(self, ws_path:str, authPermission=Depends(get_auth_permission)):
        self.jwtAuthService.pingService()

        self._check_ws_path(ws_path)
        token = self.jwtAuthService.encode_ws_token(ws_path,self.configService.CHAT_EXPIRATION)
        return JSONResponse(status_code=status.HTTP_201_CREATED,content={
            'chat-token':token,
        })


  