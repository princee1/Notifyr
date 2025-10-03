from pathlib import Path
from app.definition._service import BaseService, BuildAbortError, BuildWarningError, Service, ServiceStatus
from app.services.config_service import MODE, ConfigService
from slowapi import Limiter
from slowapi.util import get_remote_address, get_ipaddr
from app.services.database_service import RedisService
from app.services.file_service import FileService
from app.utils.fileIO import JSONFile


@Service()
class RateLimiterService(BaseService):
    
    def __init__(self,configService:ConfigService,redisService:RedisService,fileService:FileService):
        super().__init__()
        self.configService = configService
        self.redisService = redisService
        self.fileService = fileService

        self.RATE_LIMITS_PATH = Path("/run/secrets/rate_limits")

    def verify_dependency(self):
        if self.configService.MODE == MODE.PROD_MODE:
            if not self.RATE_LIMITS_PATH.exists():
                self.service_status = ServiceStatus.PARTIALLY_AVAILABLE

    def build(self,build_state=-1):

        if self.configService.MODE == MODE.DEV_MODE:
            storage_uri = None
        else:
            storage_uri = self.configService.SLOW_API_REDIS_URL

        self.GlobalLimiter = Limiter(get_ipaddr, storage_uri=storage_uri, headers_enabled=True)

        if self.configService.MODE == MODE.PROD_MODE:
            path = self.RATE_LIMITS_PATH.name
            try:
                self.rate_limits={"default":True}
                self.rate_limits= JSONFile(path).data
                self.service_status = ServiceStatus.AVAILABLE
                print(self.rate_limits)
            except:
                raise BuildWarningError(f'Could not mount the rate limiting so limit will revert too default settings')
        else:
            self.service_status = ServiceStatus.AVAILABLE
    
    async def refund(self, limit_request_id:str):
        redis = self.redisService.db[1]
        if not await self.redisService.retrieve(1,limit_request_id):
            return
        return await redis.decr(limit_request_id)
        