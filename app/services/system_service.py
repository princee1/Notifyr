from app.definition._service import BaseService, Service
from app.services.config_service import ConfigService
from app.services.database import tortoise_service
from app.services.database.redis_service import RedisService

@Service()
class SystemService(BaseService):
    
    def __init__(self,configService:ConfigService,redisService:RedisService,tortoiseService:tortoise_service):
        super().__init__()  
        self.configService = configService
        self.redisService = redisService
        self.tortoiseService = tortoise_service
    
    async def send_notification(self):
        ...
    