from app.classes.auth_permission import WSPermission
from app.definition._ws import BaseProtocol,BaseWebSocketRessource,WebSocketRessource
from fastapi import WebSocket
from app.services.config_service import ConfigService
from app.services.security_service import JWTAuthService


@WebSocketRessource
class ChatWebSocket(BaseWebSocketRessource):

    def __init__(self,jwtAuthService:JWTAuthService,configService:ConfigService):
        super().__init__()
        self.jwtAuthService = jwtAuthService
        self.configService = configService
    

    @BaseWebSocketRessource.WSEndpoint()
    def websocket_endpoint(self, websocket:WebSocket):
        ...

    def on_connect(self, websocket:WebSocket):
        auth_token = websocket.get()
        permission:WSPermission = self.jwtAuthService.decode_token(auth_token)
        ...

