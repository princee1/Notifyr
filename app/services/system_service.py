from app.definition._service import BaseService, Service
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService

@Service()
class SystemService(BaseService):
    
    def __init__(self,configService:ConfigService,redisService:RedisService):
        super().__init__()  
        self.configService = configService
        self.redisService = redisService
    
    async def send_notification(self):
        ...
    