from app.interface.llm_provider import LLMProvider
from app.services.secret_service import HCVaultService
from .config_service import ConfigService
from app.definition._service import BaseMiniService, MiniServiceStore, Service, BaseMiniServiceManager
from app.classes.secrets import ChaCha20Poly1305SecretsWrapper

@Service()
class LLMService(BaseMiniServiceManager):

    def __init__(self, configService: ConfigService,vaultService:HCVaultService) -> None:
        super().__init__()
        self.configService = configService
        self.vaultService = vaultService
        self.MiniServiceStore = MiniServiceStore[LLMProvider|BaseMiniService](self.name)

    def verify_dependency(self):
        ...

    def build(self, build_state=...):
        self._api_keys = {}
        counter = self.StatusCounter(0)
        return super().build(counter, build_state)

    @property
    def OPEN_API_KEY(self)->ChaCha20Poly1305SecretsWrapper|None:
        ...

    @property
    def DEEPSEEK_API_KEY(self)->ChaCha20Poly1305SecretsWrapper|None:
        ...

    @property
    def ANTHROPIC_API_KEY(self)->ChaCha20Poly1305SecretsWrapper|None:
        ...
    
    @property
    def GEMINI_API_KEY(self)->ChaCha20Poly1305SecretsWrapper|None:
        ...

    @property
    def COHERE_API_KEY(self)->ChaCha20Poly1305SecretsWrapper|None:
        ...

    @property
    def GROQ_API_KEY(self)->ChaCha20Poly1305SecretsWrapper|None:
        ...