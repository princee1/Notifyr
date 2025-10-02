from fastapi import WebSocket
from pydantic import BaseModel
from app.container import InjectInMethod
from app.definition._ws import BaseProtocol, WebSocketRessource, BaseWebSocketRessource
from app.services.task_service import CeleryService

@WebSocketRessource
class RedisBackendWebSocket(BaseWebSocketRessource):

    @InjectInMethod()
    def __init__(self,celeryService:CeleryService):
        super().__init__()
        self.celery_service:CeleryService = celeryService

    @BaseWebSocketRessource.WSEndpoint('notify',str)
    def redis_endpoint(websocket:WebSocket):
        ...
    
    