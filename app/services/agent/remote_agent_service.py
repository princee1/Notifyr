from app.definition._service import BaseMiniService, BaseMiniServiceManager, BaseService, MiniService, MiniServiceStore, Service
from app.errors.service_error import BuildFailureError, BuildWarningError
from app.services.config_service import ConfigService
from app.services.vault_service import VaultService
from app.services.database.mongoose_service import MongooseService
from app.utils.globals import CAPABILITIES


@MiniService()
class RemoteAgenticMiniService(BaseMiniService):
    
    def __init__(self,configService:ConfigService,):
        super().__init__(None, id)
        self.configService = configService

@Service(is_manager=True)
class RemoteAiAgentService(BaseMiniServiceManager):
    
    def __init__(self,configService:ConfigService,mongooseService:MongooseService,vaultService:VaultService):
        super().__init__()

        self.configService = configService
        self.vaultService = vaultService
        self.mongooseService = mongooseService
        self.MiniServiceStore = MiniServiceStore[RemoteAgenticMiniService](self.name)
    
    def verify_dependency(self):
        if CAPABILITIES['agent']:
            raise BuildWarningError
    
    def build(self, build_state=...):
        from grpc import aio
        import grpc_tools

