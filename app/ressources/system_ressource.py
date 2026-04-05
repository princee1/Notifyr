from app.definition._ressource import BaseHTTPRessource, HTTPRessource
from app.services import SystemService
from app.services import RedisService
from app.services import ReactiveService
from app.services.config_service import ConfigService

@HTTPRessource()
class SystemRessource(BaseHTTPRessource):
    
    def __init__(self,configService:ConfigService,reactiveService:ReactiveService,redisService:RedisService,systemService:SystemService):
        super().__init__(None,None)
        self.configService = configService
        self.reactiveService = reactiveService
        self.redisService = redisService
        self.systemService = systemService
    