from typing import Any
from fastapi import WebSocket
from app.container import InjectInMethod
from app.definition._ws import BaseWebSocketRessource,WebSocketRessource
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.health_service import HealthService

PONG ='Pong'

@WebSocketRessource
class PingPongWebSocket(BaseWebSocketRessource):

    @InjectInMethod
    def __init__(self,healthService:HealthService,redisService:RedisService,configService:ConfigService):
        super().__init__()
        self.healthService=healthService
        self.redisService = redisService
        self.configService = configService
        
    @BaseWebSocketRessource.WSEndpoint('/pong/',str,'pong-connection',)
    def pong(websocket:WebSocket,message:str):
        print(message)
        return PONG

    #@BaseWebSocketRessource.WSEndpoint('/state/',str,'app-state',)
    def state(websocket:WebSocket,message:str):
        return ''
