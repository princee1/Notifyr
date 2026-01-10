from typing import Type
from app.definition import _service
from app.models.llm_model import LLMProfileModel
from app.services.database.redis_service import RedisService
from app.services.profile_service import ProfileMiniService, ProfileService
from ..config_service import ConfigService
from app.definition._service import BaseMiniService, LinkDep, MiniService, MiniServiceStore, Service, BaseMiniServiceManager
from app.services.config_service import ConfigService
from app.services.cost_service import CostService
from app.services.logger_service import LoggerService
from app.utils.constant import LLMProviderConstant
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from llama_index.embeddings.openai import OpenAIEmbedding

@MiniService(links=[LinkDep(ProfileMiniService,to_build=True)])
class LLMProviderMiniService(BaseMiniService):
    
    def __init__(self,configService:ConfigService,profileMiniService:ProfileMiniService[LLMProfileModel]):
        self.depService = profileMiniService
        self.configService = configService
        super().__init__(profileMiniService,None)

    @property
    def model(self) -> LLMProfileModel:
        return self.depService.model
    
    def build(self, build_state = ...):
        api_key =self.depService.credentials.to_plain()

        embedding = self.model.embedding_models.model_dump()
        match self.model.provider:
            case 'anthropic':
                ...
            
            case 'cohere':
                ...

            case 'deepseek':
                ...
            
            case 'gemini':
                ...
            
            case 'groq':
                ...
            
            case 'ollama':
                ...
            case 'openai':
                self.embedding_model = OpenAIEmbedding(api_key=api_key,**embedding)
                self.embedding_search_model= OpenAIEmbedding(api_key=api_key,**embedding)
    
    def factory(self,model:str,temperature:float,timeout:float,**kwargs)->BaseChatModel:
        api_key =lambda: self.depService.credentials.to_plain()
        match self.model.provider:
            case 'anthropic':
                return 
            
            case 'cohere':
                return

            case 'deepseek':
                return
            
            case 'gemini':
                return
            
            case 'groq':
                return
            
            case 'ollama':
                return
            
            case 'openai':
                return ChatOpenAI()

@Service(is_manager=True,links=[LinkDep(ProfileService,to_build=True)])
class LLMProviderService(BaseMiniServiceManager):
    
    def __init__(self,profileService:ProfileService,loggerService:LoggerService,configService:ConfigService):
        super().__init__()
        self.profileService = profileService
        self.configService = configService
        self.loggerService = loggerService

        self.MiniServiceStore = MiniServiceStore[LLMProviderMiniService](self.name)

    def build(self, build_state=...):
        
        count = self.profileService.MiniServiceStore.filter_count(lambda p: p.model.__class__ == LLMProfileModel )
        state_counter = self.StatusCounter(count)

        self.MiniServiceStore.clear()

        for i,p in self.profileService.MiniServiceStore:
            if p.model.__class__ != LLMProfileModel:
                continue
            provider = LLMProviderMiniService(
                self.configService,
                p
            )

            provider._builder(_service.BaseMiniService.QUIET_MINI_SERVICE,build_state,self.CONTAINER_LIFECYCLE_SCOPE)
            state_counter.count(provider)
            self.MiniServiceStore.add(provider)

        super().build(state_counter)
    
