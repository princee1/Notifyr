from typing import Literal, TypedDict

import requests
from app.definition import _service
from app.errors.llm_error import LLMConfigNotConfiguredError
from app.errors.service_error import BuildFailureError, BuildOkError, BuildWarningError
from app.models.llm_model import (
    EMBEDDER_PROVIDER_SET, LLMProfileModel, 
    VectorEmbeddingConfig, CrawlLLMConfig, WebResearchConfig, 
    GraphitiLLMConfig, GraphitiEmbeddingConfig,
    VALID_EMBEDDING_MODELS, DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
)
from app.services.profile_service import ProfileMiniService, ProfileService
from app.utils.constant import LLMProviderConstant
from ..config_service import ConfigService
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, LinkDep, MiniService, MiniServiceStore, Service, BaseMiniServiceManager, ServiceStatus
from app.services.config_service import ConfigService
from app.services.logger_service import LoggerService


class GraphitiConfig(TypedDict):
    client:str
    embedding:str
    reranker:str

class VectorConfig(TypedDict):
    embedding:str

class CrawlConfig(TypedDict):
    llmConfig:str

class ResearchConfig(TypedDict):
    llmConfig:str
    

class VerifyLLMConfig(TypedDict):
    graphiti:bool
    vector:bool
    crawl:bool
    research:bool


PROVIDERS = {
    "openai": {
        "url": "https://api.openai.com/v1/models",
        "headers": lambda key: {"Authorization": f"Bearer {key}"}
    },
    "anthropic": {
        "url": "https://api.anthropic.com/v1/models",
        "headers": lambda key: {
            "x-api-key": key,
            "anthropic-version": "2023-06-01"
        }
    },
    "cohere": {
        "url": "https://api.cohere.com/v1/models",
        "headers": lambda key: {"Authorization": f"Bearer {key}"}
    },
    "groq": {
        "url": "https://api.groq.com/openai/v1/models",
        "headers": lambda key: {"Authorization": f"Bearer {key}"}
    },
    "deepseek": {
        "url": "https://api.deepseek.com/v1/models",
        "headers": lambda key: {"Authorization": f"Bearer {key}"}
    }
}
LLM_VALIDATION_TIMEOUT=5

@MiniService(links=[LinkDep(ProfileMiniService,to_build=True)])
class LLMProviderMiniService(BaseMiniService):
    
    def __init__(self,configService:ConfigService,profileMiniService:ProfileMiniService[LLMProfileModel]):
        self.depService = profileMiniService
        self.configService = configService
        super().__init__(profileMiniService,None)

    @property
    def model(self) -> LLMProfileModel:
        return self.depService.model
    
    def build(self, build_state = DEFAULT_BUILD_STATE):
        
        provider = self.model.provider.lower()
        api_key = self.depService.credentials.to_plain()

        if provider not in PROVIDERS:
            raise BuildFailureError(f"Unsupported provider: {provider}")

        config = PROVIDERS[provider]

        try:
            r = requests.get(
                config["url"],
                headers=config["headers"](api_key),
                timeout=LLM_VALIDATION_TIMEOUT
            )
            match r.status_code:
                case 200:
                    return
                case 401:
                    raise BuildFailureError('Api Key not valid')
                case 403:
                    raise BuildWarningError('Api Key valid but not authorized')
                
        except requests.Timeout as e:
            raise BuildOkError('Could not connect to the endpoint at the moment')
        except requests.RequestException as e:
            raise BuildFailureError('Cant verify the llm configuration')
            
    def create_default_configs(self, variable: Literal['vector_embedding_config', 'crawl_config','research_config','graph_config',
                                                       'graph_embedding_config', 'graph_reranker_config']) -> None:
        """
        Create a copy of the current model with missing configs populated with defaults.
        Validates the new model before returning.
        Uses the appropriate Config model instead of dicts.
        """
        model_data = self.model.model_dump()

        match variable:
            case 'vector_embedding_config':
                if model_data.get('vector_embedding_config') is None and self.model.provider in EMBEDDER_PROVIDER_SET:
                    embedding_models = VALID_EMBEDDING_MODELS.get(self.model.provider, [])
                    if embedding_models:
                        model_data['vector_embedding_config'] = VectorEmbeddingConfig(
                            model=embedding_models[0],
                            max_retries=10,
                            timeout=60.0,
                            batch_size=100
                        ).model_dump()
                    
            case 'crawl_config':
                crawl_models = LLMProviderConstant.CRAWL4AI_MODELS.get(self.model.provider, [])
                if model_data.get('crawl_config') is None and crawl_models:
                    model_data['crawl_config'] = CrawlLLMConfig(
                        model=self.model.default_model or crawl_models[0],
                        temperature=0.7,
                        max_tokens=2048,
                        top_p=0.9
                    ).model_dump()

            case 'research_config':
                if model_data.get('research_config') is None and self.model.provider in EMBEDDER_PROVIDER_SET:
                    embedding_models = VALID_EMBEDDING_MODELS.get(self.model.provider, [])
                    if embedding_models:
                        model_data['research_config'] = WebResearchConfig(
                                embedding_model=embedding_models[0],
                                max_tokens=self.model.max_output_tokens,
                            )

            case 'graph_config':
                if model_data.get('graph_config') is None:
                    model_data['graph_config'] = GraphitiLLMConfig(
                        model=self.model.default_model or LLMProviderConstant.MODELS[self.model.provider]['default'],
                        temperature=DEFAULT_TEMPERATURE,
                        max_tokens=DEFAULT_MAX_TOKENS,
                        cache=False
                    ).model_dump()

            case 'graph_embedding_config':
                if model_data.get('graph_embedding_config') is None and self.model.provider in EMBEDDER_PROVIDER_SET:
                    embedding_models = VALID_EMBEDDING_MODELS.get(self.model.provider, [])
                    if embedding_models:
                        model_data['graph_embedding_config'] = GraphitiEmbeddingConfig(
                            embedding_model=embedding_models[0],
                            embedding_dim=1024,
                            batch=100
                        ).model_dump()

            case 'graph_reranker_config':
                if model_data.get('graph_reranker_config') is None:
                    model_data['graph_reranker_config'] = GraphitiLLMConfig(
                        model=self.model.default_model or LLMProviderConstant.MODELS[self.model.provider]['default'],
                        temperature=0.5,
                        max_tokens=512,
                        cache=False
                    ).model_dump()
            
            case _:
                pass

        self.depService.update_model(model_data)

@Service(is_manager=True,links=[LinkDep(ProfileService,to_build=True)])
class LLMProviderService(BaseMiniServiceManager):
    
    def __init__(self,profileService:ProfileService,loggerService:LoggerService,configService:ConfigService):
        super().__init__()
        self.profileService = profileService
        self.configService = configService
        self.loggerService = loggerService

        self.MiniServiceStore = MiniServiceStore[LLMProviderMiniService](self.name)

    def build(self, build_state=...):

        self.graphiti_config: GraphitiConfig = {}
        self.vector_config: VectorConfig = {}
        self.crawl_config: CrawlConfig = {}
        self.research_config: ResearchConfig = {}

        fallback_providers = {
            'graphiti': None,
            'vector': None,
            'crawl': None,
            'research': None
        }
        
        count = self.profileService.MiniServiceStore.filter_count(lambda p: p.model.__class__ == LLMProfileModel )
        state_counter = self.StatusCounter(count)

        self.MiniServiceStore.clear()

        for i,p in self.profileService.MiniServiceStore:
            if p.model.__class__ != LLMProfileModel:
                continue
            llm_provider = LLMProviderMiniService(
                self.configService,
                p
            )
            llm_provider._builder(_service.BaseMiniService.QUIET_MINI_SERVICE,build_state,self.CONTAINER_LIFECYCLE_SCOPE)
            state_counter.count(llm_provider)
            self.MiniServiceStore.add(llm_provider)

            if llm_provider.service_status != ServiceStatus.AVAILABLE:
                continue
            
            ##########################################           #############################################

            if llm_provider.model.crawl_config != None and not self.crawl_config.get('llmConfig',None):
                self.crawl_config['llmConfig'] = llm_provider.miniService_id

            elif not fallback_providers['crawl']:
                if LLMProviderConstant.CRAWL4AI_MODELS.get(llm_provider.model.provider,None):
                    fallback_providers['crawl'] = llm_provider.miniService_id

            ##########################################           #############################################

            if llm_provider.model.research_config != None and not self.research_config.get('llmConfig',None):
                self.research_config['llmConfig'] = llm_provider.miniService_id

            elif not fallback_providers['research']:
                if llm_provider.model.provider in EMBEDDER_PROVIDER_SET:
                    fallback_providers['research'] = llm_provider.miniService_id

            ##########################################           #############################################
            

            if llm_provider.model.vector_embedding_config != None and not self.vector_config.get('embedding',None):
                if llm_provider.model.provider in EMBEDDER_PROVIDER_SET:
                    self.vector_config['embedding'] = llm_provider.miniService_id

            elif not fallback_providers['vector']:
                if llm_provider.model.provider in EMBEDDER_PROVIDER_SET:
                    fallback_providers['vector'] = llm_provider.miniService_id

            ##########################################           #############################################

            if llm_provider.model.graph_config != None and not self.graphiti_config.get('client',None):
                if llm_provider.model.provider in EMBEDDER_PROVIDER_SET:
                    fallback_providers['graphiti'] = llm_provider.miniService_id

                self.graphiti_config['client'] = llm_provider.miniService_id
            elif not fallback_providers['graphiti']:
                if llm_provider.model.provider in EMBEDDER_PROVIDER_SET:
                    fallback_providers['graphiti'] = llm_provider.miniService_id
            
            ##########################################           #############################################
            
            if llm_provider.model.graph_embedding_config != None and not self.graphiti_config.get('embedding',None):
                self.graphiti_config['embedding'] = llm_provider.miniService_id
            
            if llm_provider.model.graph_reranker_config != None and not self.graphiti_config.get('reranker',None): 
                self.graphiti_config['reranker'] = llm_provider.miniService_id

        # Ensure all required configs are populated
        self._ensure_config(fallback_providers)
        
        super().build(state_counter)

    async def pingService(self, infinite_wait, data, profile = None, as_manager = False, **kwargs):

        if kwargs.get('graphiti',True) and len(self.graphiti_config) < 1:
            raise LLMConfigNotConfiguredError('graphiti')

        if kwargs.get('vector',True) and len(self.vector_config) < 1:
            raise LLMConfigNotConfiguredError('vector')

        if kwargs.get('crawl',True) and len(self.crawl_config) < 1:
            raise LLMConfigNotConfiguredError('crawl')
        
        if kwargs.get('research',True) and len(self.research_config) < 1:
            raise LLMConfigNotConfiguredError('research')

    def _ensure_config(self, fallback_providers: dict[Literal['graphiti','vector','crawl','research'], str]):
        """
        Ensure all required configs are populated. If missing, use fallback provider
        or create default configs from a provider with all configs defined.
        """

        error = []
        
        # Graphiti config (client, embedding, reranker)
        if not self.graphiti_config.get('embedding',None):
            if fallback_providers['graphiti']:
                self.graphiti_config['embedding'] = fallback_providers['graphiti']
                self.MiniServiceStore.get(fallback_providers['graphiti']).create_default_configs('graph_embedding_config')
            else:
                error.append('No provider available for graphiti embedding config')
        
        if not self.graphiti_config.get('reranker',None):
            if fallback_providers['graphiti']:
                self.graphiti_config['reranker'] = fallback_providers['graphiti']
                self.MiniServiceStore.get(fallback_providers['graphiti']).create_default_configs('graph_reranker_config')
            else:
                error.append('No provider available for graphiti reranker config')
    
        # Vector config
        if not self.vector_config.get('embedding',None):
            if fallback_providers['vector']:
                self.vector_config['embedding'] = fallback_providers['vector']
                self.MiniServiceStore.get(fallback_providers['vector']).create_default_configs('vector_embedding_config')
            else:
                error.append('No provider available for vector embedding config')
        
        # Crawl config
        if not self.crawl_config.get('llmConfig',None):
            if fallback_providers['crawl']:
                self.crawl_config['llmConfig'] = fallback_providers['crawl']
                self.MiniServiceStore.get(fallback_providers['crawl']).create_default_configs('crawl_config')
            else:
                error.append('No provider available for crawl config')
        
        # Research config
        if not self.research_config.get('llmConfig',None):
            if fallback_providers['research']:
                self.research_config['llmConfig'] = fallback_providers['research']
                self.MiniServiceStore.get(fallback_providers['research']).create_default_configs('research_config')
            else:
                error.append('No provider available for research config')
