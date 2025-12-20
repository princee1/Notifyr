from app.services.profile_service import ProfileService
from app.interface.llm_provider import LLMProvider
from ..config_service import ConfigService
from app.definition._service import BaseMiniService, MiniService, MiniServiceStore, Service, BaseMiniServiceManager
from app.interface.llm_provider import LLMProvider
from app.services.config_service import ConfigService
from app.services.cost_service import CostService
from app.services.logger_service import LoggerService
from app.utils.constant import LLMProviderConstant
from openai import OpenAI,AsyncOpenAI

def OPEN_API_KEY(self)->None:
    ...

def DEEPSEEK_API_KEY(self)->None:
    ...

def ANTHROPIC_API_KEY(self)->None:
    ...

def GEMINI_API_KEY(self)->None:
    ...

def COHERE_API_KEY(self)->None:
    ...

def GROQ_API_KEY(self)->None:
    ...


@MiniService()
class OpenAIProviderMiniService(BaseMiniService,LLMProvider):

    def __init__(self,configService:ConfigService,costService:CostService,loggerService:LoggerService):
        super().__init__(None,LLMProviderConstant.OPENAI)
        self.configService = configService
        self.loggerService = loggerService
        self.costService = costService
    

    def build(self, build_state = ...):
        self.client = OpenAI()
        

@Service(is_manager=True)
class LLMProviderService(BaseMiniServiceManager):
    
    def __init__(self,profileService:ProfileService,costService:CostService,loggerService:LoggerService,configService:ConfigService):
        super().__init__()
        self.profileService = profileService
        self.MiniServiceStore = MiniServiceStore[LLMProvider|BaseMiniService](self.name)

    def build(self, build_state=...):
        ...