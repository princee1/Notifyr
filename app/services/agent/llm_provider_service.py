from pydantic import SecretStr
from app.definition import _service
from app.models.agents_model import AgentModel
from app.models.llm_model import LLMProfileModel
from app.services.profile_service import ProfileMiniService, ProfileService
from ..config_service import ConfigService
from app.definition._service import BaseMiniService, LinkDep, MiniService, MiniServiceStore, Service, BaseMiniServiceManager
from app.services.config_service import ConfigService
from app.services.logger_service import LoggerService
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_cohere import ChatCohere
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
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

        embedding_search = self.model.embedding_search.model_dump()
        embedding_parse = self.model.embedding_parse.model_dump()

        match self.model.provider:
            case 'anthropic':
                ...
            
            case 'cohere':
                ...
            
            case 'gemini':
                ...
            
            case 'groq':
                ...
            
            case 'ollama':
                ...
            case 'openai' | 'deepseek':
                self.embedding_search_model = OpenAIEmbedding(api_key=api_key,**embedding_search)
                self.embedding_parse_model= OpenAIEmbedding(api_key=api_key,**embedding_parse)
    
    def ChatAgentFactory(self,agentModel:AgentModel)->BaseChatModel:
        api_key =lambda: self.depService.credentials.to_plain()

        max_output_token = self.model.max_output_tokens
        max_tokens = agentModel.max_tokens
        if max_output_token:
            max_tokens = max_output_token

        provider = self.model.provider
        match provider:
            case 'anthropic': 
                return ChatAnthropic(
                    streaming=True,
                    model_name=agentModel.model,
                    max_retries=agentModel.max_retries,
                    temperature=agentModel.temperature,
                    top_p=agentModel.top_p,
                    top_k=agentModel.top_k,
                    timeout=agentModel.timeout,
                    effort=agentModel.effort,
                    anthropic_proxy=agentModel.proxy_url
                )
            
            case 'cohere': 
                return ChatCohere(
                    streaming=True,
                    temperature=agentModel.temperature,
                    model=agentModel.model,
                    cohere_api_key=SecretStr(api_key()),
                    timeout_seconds=agentModel.timeout, 
                )

            case 'deepseek'| 'openai':
                return ChatOpenAI(
                    streaming=True,
                    max_completion_tokens=max_tokens,
                    api_key=api_key,
                    base_url="https://api.deepseek.com" if provider == 'deepseek' else None,
                    temperature=agentModel.temperature,
                    max_retries=agentModel.max_retries,
                    timeout=agentModel.timeout,
                    top_p=agentModel.top_p,
                    model=agentModel.model,
                    frequency_penalty=agentModel.frequency_penalty,
                    presence_penalty=agentModel.presence_penalty,
                    n=agentModel.n,
                    reasoning_effort=agentModel.effort,
                    openai_proxy=agentModel.proxy_url
            )
            
            case 'gemini': raise NotImplementedError()
            
            case 'groq': 
                return ChatGroq(
                    streaming=True,
                    max_tokens=max_tokens,
                    max_retries=agentModel.max_retries,
                    timeout=agentModel.timeout,
                    n=agentModel.n,
                    api_key=api_key,
                    model=agentModel.model,
                    temperature=agentModel.temperature,
                    groq_proxy=agentModel.proxy_url,
                    reasoning_effort=agentModel.effort,
                    reasoning_format=agentModel.reasoning_format
                )
            
            case 'ollama':
                raise NotImplementedError()
                return ChatOllama()

    def ChatDataFactory(self,)->BaseChatModel:
        ...

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
    
