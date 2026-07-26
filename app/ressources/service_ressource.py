from app.definition._ressource import BaseHTTPRessource, UsePermission
from app.services.config_service import ConfigService, WorkerService
from app.services.database.redis_service import RedisService


class ServiceRessource(BaseHTTPRessource):
    
    def __init__(self, configService:ConfigService,redisService:RedisService,workerService:WorkerService):
        super().__init__()
        self.redisService = redisService
        self.workerService = workerService
        self.configService = configService
    
    async def database_status(self):
        ...

    async def worker_status(self):
        ...

    async def ntfr_status(self):
        ...
    
    async def agent_status(self):
        ...
    
    async def other_status(self):
        ...
    
    async def all_status(self):
        ...

