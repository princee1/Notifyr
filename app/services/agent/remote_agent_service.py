from app.definition._service import BaseMiniService, BaseMiniServiceManager, BaseService, MiniService, MiniServiceStore, Service
from app.services.config_service import ConfigService
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
        self.MiniServiceStore = MiniServiceStore[RemoteAgenticMiniService](self.name)
    
    def build(self, build_state=...):
        ...