from pathlib import Path
from app.definition._service import BaseService, BuildAbortError, BuildWarningError, Service, ServiceStatus
from app.errors.service_error import BuildFailureError
from app.services.config_service import MODE, ConfigService
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.services.database_service import RedisService
from app.services.file_service import FileService
from app.utils.constant import RedisConstant
from app.utils.fileIO import JSONFile
from app.classes.auth_permission import AuthPermission

@Service()
class CostService(BaseService):
    
    def __init__(self,configService:ConfigService,redisService:RedisService,fileService:FileService):
        super().__init__()
        self.configService = configService
        self.redisService = redisService
        self.fileService = fileService

        self.RATE_LIMITS_PATH = Path("/run/secrets/costs")


    def verify_dependency(self):
        if self.configService.MODE == MODE.PROD_MODE:
            if not self.RATE_LIMITS_PATH.exists():
                self.service_status = ServiceStatus.PARTIALLY_AVAILABLE
        
        if self.redisService.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError

    def build(self,build_state=-1):

        storage_uri = None if self.configService.MODE == MODE.DEV_MODE else self.configService.SLOW_API_REDIS_URL

        self.GlobalLimiter = Limiter(get_remote_address, storage_uri=storage_uri, headers_enabled=True)
        
        if self.configService.MODE == MODE.PROD_MODE:
            path = self.RATE_LIMITS_PATH.name
            try:
                self.rate_limits={"default":True}
                self.rate_limits= JSONFile(path).data
                self.service_status = ServiceStatus.AVAILABLE
            except:
                raise BuildWarningError(f'Could not mount the rate limiting so limit will revert too default settings')
        else:
            self.service_status = ServiceStatus.AVAILABLE
    
    async def refund(self, limit_request_id:str):
        redis = self.redisService.db[1]
        if not await self.redisService.retrieve(1,limit_request_id):
            return
        return await redis.decr(limit_request_id)
    
    async def limiter_startup(self):
        # await self._init_key()
        # await self._init_key()
        # await self._init_key()
        # await self._init_key()
        # await self._init_key()
        ...

    async def _init_key(self,name:str,default:int,expiration:int|float = 0):
        if await self.redisService.exists(RedisConstant.LIMITER_DB,name):
            return 
        await self.redisService.store(RedisConstant.LIMITER_DB,name,default,expiration)

    async def verify_limit(self,name:str,cost:int):
        ...