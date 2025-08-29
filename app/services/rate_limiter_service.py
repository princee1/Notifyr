from app.definition._service import BaseService, Service
from app.services.config_service import MODE, ConfigService
from slowapi import Limiter
from slowapi.util import get_remote_address, get_ipaddr
from app.services.database_service import RedisService

@Service
class RateLimiterService(BaseService):
    
    def __init__(self,configService:ConfigService,redisService:RedisService):
        super().__init__()
        self.configService = configService
        self.redisService = redisService

    def build(self,build_state=-1):

        if self.configService.MODE == MODE.DEV_MODE:
            storage_uri = None
        else:
            storage_uri = self.configService.SLOW_API_REDIS_URL

        self.GlobalLimiter = Limiter(get_ipaddr, storage_uri=storage_uri, headers_enabled=True)
    
    async def refund(self, limit_request_id:str):
        redis = self.redisService.db[1]
        if not await self.redisService.retrieve(1,limit_request_id):
            return
        return await redis.decr(limit_request_id)
        