from app.definition._service import BaseMiniService, BaseMiniServiceManager, BaseService, MiniService, MiniServiceStore, Service
from app.errors.service_error import BuildFailureError
from app.services.config_service import ConfigService
from app.services.secret_service import HCVaultService
from app.services.database.mongoose_service import MongooseService
from app.utils.globals import CAPABILITIES


@MiniService()
class RemoteAgenticMiniService(BaseMiniService):
    
    def __init__(self,configService:ConfigService,):
        super().__init__(None, id)
        self.configService = configService

@Service()
class RemoteAiAgentService(BaseMiniServiceManager):
    
    def __init__(self,configService:ConfigService,mongooseService:MongooseService,vaultService:HCVaultService):
        super().__init__()

        self.configService = configService
        self.vaultService = vaultService
        self.mongooseService = mongooseService
        self.MiniServiceStore = MiniServiceStore[RemoteAgenticMiniService](self.name)
    
    def verify_dependency(self):
        if CAPABILITIES['webhook']:
            ...
            #raise BuildFailureError
    
    def build(self, build_state=...):
        from grpc import aio
        import grpc_tools

