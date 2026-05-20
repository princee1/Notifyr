import time
from typing import Any
from app.classes.auth_permission import WSPermission
from app.container import InjectInMethod
from app.definition._ws import BaseProtocol,BaseWebSocketRessource,WebSocketRessource
from fastapi import HTTPException, WebSocket
from app.services.chat_service import ChatService
from app.services.config_service import ConfigService
from app.services.ntfr.live_chat_service import LiveChatService
from app.services.security_service import JWTAuthService


@WebSocketRessource
class LiveChatWebSocket(BaseWebSocketRessource):

    @InjectInMethod()
    def __init__(self,configService:ConfigService,liveChatService:LiveChatService):
        super().__init__()
        self.configService = configService
        self.liveChatService = liveChatService
    

    @BaseWebSocketRessource.WSEndpoint('/live-chat')
    def websocket_endpoint(self, websocket:WebSocket,message:Any):
        ...

    

