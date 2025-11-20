from app.interface.ai_driver import AIDriver
from app.services.secret_service import HCVaultService
from .config_service import ConfigService
from app.definition._service import BaseMiniService, MiniServiceStore, Service, BaseMiniServiceManager

@Service()
class LLMModelService(BaseMiniServiceManager):

    def __init__(self, configService: ConfigService,vaultService:HCVaultService) -> None:
        super().__init__()
        self.configService = configService
        self.vaultService = vaultService
        self.MiniServiceStore = MiniServiceStore[AIDriver|BaseMiniService](self.name)

    def verify_dependency(self):
        ...

    def build(self, build_state=...):
        self._api_keys = {}
        counter = self.StatusCounter(0)
        return super().build(counter, build_state)

    @property
    def OPEN_API_KEY(self)->str|None:
        ...

    @property
    def DEEPSEEK_API_KEY(self)->str|None:
        ...

    @property
    def ANTHROPIC_API_KEY(self)->str|None:
        ...
    
    @property
    def GEMINI_API_KEY(self)->str|None:
        ...