from fastapi import Depends
from  app.definition._ressource import BaseHTTPRessource,HTTPRessource, IncludeWebsocket, UseHandler, UsePermission, UseRoles
from app.services.config_service import ConfigService
from app.services.security_service import JWTAuthService
from app.websockets.chat_ws import ChatWebSocket
from app.decorators.handlers import ServiceAvailabilityHandler
from app.classes.auth_permission import WSPermission,Role
from app.decorators.permissions import JWTRouteHTTPPermission
from app.utils.dependencies import get_auth_permission


CHAT_PREFIX= 'chat'

#@IncludeWebsocket(ChatWebSocket)
@UseRoles([Role.CHAT])
@UseHandler(ServiceAvailabilityHandler)
@HTTPRessource(prefix=CHAT_PREFIX,websockets=[ChatWebSocket])
class LiveChatRessource(BaseHTTPRessource):
    
    def __init__(self,jwtAuthService:JWTAuthService,configService:ConfigService):
        super().__init__()
        self.jwtAuthService = jwtAuthService
        self.configService = configService

    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.Get('/invoke-permission')
    def invoke_chat_permission(self, authPermission=Depends(get_auth_permission)):
        ...
    
