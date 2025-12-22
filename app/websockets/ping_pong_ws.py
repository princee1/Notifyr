from typing import Any
from fastapi import WebSocket
from app.container import InjectInMethod
from app.definition._ws import BaseWebSocketRessource,WebSocketRessource
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from app.services.health_service import HealthService

PONG =b'PONG'

@WebSocketRessource
class PingPongWebSocket(BaseWebSocketRessource):

    @InjectInMethod()
    def __init__(self,healthService:HealthService,redisService:RedisService,configService:ConfigService):
        super().__init__()
        self.healthService=healthService
        self.redisService = redisService
        self.configService = configService
        
    @BaseWebSocketRessource.WSEndpoint('/pong/',str,'pong-connection',prefix='')
    def pong(self,websocket:WebSocket,message:str):
        return PONG

    #@BaseWebSocketRessource.WSEndpoint('/state/',str,'app-state',)
    def state(self,websocket:WebSocket,message:str):
        return ''
