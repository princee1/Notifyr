from app.services.profile_service import ProfileService
from ..config_service import ConfigService
from app.definition._service import BaseMiniService, MiniService, MiniServiceStore, Service, BaseMiniServiceManager
from app.services.config_service import ConfigService
from app.services.cost_service import CostService
from app.services.logger_service import LoggerService
from app.utils.constant import LLMProviderConstant


class LLMProviderMiniService(BaseMiniService):
    
    def __init__(self,profileService:ProfileService,model_id:str):
        self.profileService = profileService

    def build(self, build_state = ...):
        super().build(build_state)
        # Additional build steps can be added here


@Service(is_manager=True)
class LLMProviderService(BaseMiniServiceManager):
    
    def __init__(self,profileService:ProfileService,costService:CostService,loggerService:LoggerService,configService:ConfigService):
        super().__init__()
        self.profileService = profileService
        self.MiniServiceStore = MiniServiceStore[LLMProviderMiniService](self.name)

    def build(self, build_state=...):
        ...