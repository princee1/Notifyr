from app.definition._service import BaseMiniService, BaseMiniServiceManager, BaseService, MiniService, Service
from app.services.config_service import ConfigService
from httpx import AsyncClient
from app.services.database.mongoose_service import MongooseService


@MiniService()
class RemoteAgenticMiniService(BaseMiniService):
    
    def __init__(self,configService:ConfigService,):
        super().__init__(None, id)
        self.configService = configService


@Service()
class RemoteAiAgentService(BaseMiniServiceManager):
    
    def __init__(self,configService:ConfigService,mongooseService:MongooseService):
        super().__init__()

        self.configService = configService
        self.mongooseService = mongooseService