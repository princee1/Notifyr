from app.container import InjectInMethod
from app.definition._ws import BaseWebSocketRessource,WebSocketRessource
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.health_service import HealthService

@WebSocketRessource
class PingPongWebSocket(BaseWebSocketRessource,):

    @InjectInMethod
    def __init__(self,healthService:HealthService,redisService:RedisService,configService:ConfigService):
        super().__init__()
        self.healthService=healthService
        self.redisService = redisService
        self.configService = configService

    
    
        
