from app.definition._service import BaseService, Service
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from app.services.database.tortoise_service import TortoiseConnectionService
from app.services.logger_service import LoggerService

@Service()
class SystemService(BaseService):
    
    def __init__(self,configService:ConfigService,loggerService:LoggerService,redisService:RedisService,tortoiseService:TortoiseConnectionService):
        super().__init__()  
        self.configService = configService
        self.redisService = redisService
        self.tortoiseService = tortoiseService
        self.loggerService = loggerService
    
    async def send_notification(self):
        ...
    