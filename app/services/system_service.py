from app.definition._service import BaseService, Service
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from app.services.database.tortoise_service import TortoiseConnectionService
@Service()
class SystemService(BaseService):
    
    def __init__(self,configService:ConfigService,redisService:RedisService,tortoiseService:TortoiseConnectionService):
        super().__init__()  
        self.configService = configService
        self.redisService = redisService
        self.tortoiseService = tortoiseService
    
    async def send_notification(self):
        ...
    