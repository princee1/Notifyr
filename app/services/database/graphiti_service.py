from typing import Any, Dict, Iterator, Type
from app.definition._service import DEFAULT_BUILD_STATE, BaseService, LinkDep, Service, ServiceStatus
from app.errors.service_error import BuildError, BuildFailureError, BuildNotImplementedError
from app.services.agent.llm_provider_service import LLMProviderMiniService, LLMProviderService
from app.services.config_service import ConfigService, UvicornWorkerService
from app.services.cost_service import CostService
from app.services.database.mongoose_service import MongooseService
from app.services.vault_service import VaultService
from neo4j import AsyncGraphDatabase,GraphDatabase

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.cross_encoder.gemini_reranker_client import GeminiRerankerClient
from graphiti_core.embedder.gemini import GeminiEmbedder,GeminiEmbedderConfig
from graphiti_core.embedder.openai import OpenAIEmbedder,OpenAIEmbedderConfig

from graphiti_core.llm_client.anthropic_client import AnthropicClient
from graphiti_core.llm_client.groq_client import GroqClient
from graphiti_core.llm_client.gemini_client import GeminiClient
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.llm_client.client import LLMClient 
from graphiti_core.llm_client.config import LLMConfig

from app.utils.constant import LLMProviderConstant


CLIENT_MAP:Dict[LLMProviderConstant.LLMProvider,Type[LLMClient]] = {
    'groq':GroqClient,'gemini':GeminiClient,'openai':OpenAIClient,'anthropic':AnthropicClient,'deepseek':OpenAIGenericClient
}

GRAPHITI_BUILD_STATE = 421

@Service(
    links=[LinkDep(service=LLMProviderService,to_build=True,build_state=GRAPHITI_BUILD_STATE)]
)
class GraphitiService(BaseService):
    
    def __init__(self,configService:ConfigService,uvicornWorkerService:UvicornWorkerService,vaultService:VaultService,mongooseService:MongooseService,llmProviderService:LLMProviderService,customService:CostService):
        super().__init__()
        self.configService = configService
        self.uvicornWorkerService = uvicornWorkerService
        self.vaultService = vaultService
        self.mongooseService = mongooseService
        self.llmProviderService = llmProviderService
        self.customService = customService
    
    def build(self, build_state = DEFAULT_BUILD_STATE):
        try:
            if build_state == DEFAULT_BUILD_STATE:
                self.client = AsyncGraphDatabase().driver(self.uri,auth=('neo4j','password'))
                client = GraphDatabase.driver(self.uri,auth=('neo4j','password'),user_agent=self.uvicornWorkerService.INSTANCE_ID)
                client.verify_connectivity()
                client.verify_authentication()
            
            providers = self._setup_llm_provider()
            llm_client,embedding,cross_encoder = self._initialize_graphiti_llm(*providers)
            self.graphiti = Graphiti(self.uri,'neo4j','password',llm_client=llm_client,embedder=embedding,cross_encoder=cross_encoder,max_coroutines=self.configService.GRAPHITI_MAX_COROUTINES)

        except BuildError as e:
            raise e
        except Exception as e:
            raise BuildFailureError(str(e))
        finally:
            client.close()

    async def close(self):
        await self.graphiti.close()

    async def search(self):
        ...
    
    async def center_search(self):
        ...

    async def add_content(self,name:str,body:dict):
        result = await self.graphiti.add_episode(
            source=EpisodeType.json
        )

    async def add_text(self,name:str,body:str):
        result = await self.graphiti.add_episode(
            source=EpisodeType.text
        )

    async def add_message(self):
        result = await self.graphiti.add_episode(
            source=EpisodeType.message
        )
  
    async def bulk_add_episode(self, iterator:Iterator[Any],episode_type:EpisodeType):
        ...
    
    async def init_database(self,):
        ...

    def _setup_llm_provider(self):

        provider_config = self.llmProviderService.graphiti_config

        llm_client_provider = provider_config.get('client', None)
        embedding_provider = provider_config.get('embedding', None)
        reranker_provider = provider_config.get('reranker', None)

        if llm_client_provider is None:
            raise BuildFailureError('Graphiti LLM client provider is not specified in the configuration.')
        
        if embedding_provider is None:
            raise BuildFailureError('Graphiti Embedding provider is not specified in the configuration.')
        
        if reranker_provider is None:
            raise BuildFailureError('Graphiti Reranker provider is not specified in the configuration.')
        
        llm_client_provider = self.llmProviderService.MiniServiceStore.get(llm_client_provider)
        if llm_client_provider.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError(f'Graphiti LLM client provider MiniService is not available.: {llm_client_provider.miniService_id}')
        
        embedding_provider = self.llmProviderService.MiniServiceStore.get(embedding_provider)
        if embedding_provider.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError(f'Graphiti Embedding provider MiniService is not available.: {embedding_provider.miniService_id}')

        reranker_provider = self.llmProviderService.MiniServiceStore.get(reranker_provider)
        if reranker_provider.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError(f'Graphiti Reranker provider MiniService is not available.: {reranker_provider.miniService_id}')
        
        llm_client_provider.add_used_services(self)
        embedding_provider.add_used_services(self)
        reranker_provider.add_used_services(self)

        return llm_client_provider,embedding_provider,reranker_provider

    def _initialize_graphiti_llm(self,llm_client_provider:LLMProviderMiniService,embedding_provider:LLMProviderMiniService,reranker_provider:LLMProviderMiniService):
    
        llm_config =LLMConfig(
                        api_key=llm_client_provider.depService.credentials.to_plain()['api_key'],
                        **llm_client_provider.model.graph_config.model_dump(exclude=('reasoning','verbosity','cache'))
                    )

        match llm_client_provider.model.provider:
            case 'groq' | 'anthropic' | 'deepseek'|'gemini':
                cls = CLIENT_MAP[llm_client_provider.model.provider]
                llm_client = cls(
                    cache=llm_client_provider.model.graph_config.cache,
                    config=llm_config
                )  
            case 'openai':
                llm_client = OpenAIClient(
                    config=llm_config,
                    **llm_client_provider.model.graph_config.model_dump(include=('reasoning','verbosity','cache'))
                )
            case _:
                raise BuildFailureError(f'LLM Client provider Mini Service is not supported: provider {llm_client_provider.model.provider} id: {llm_client_provider.miniService_id}')

        match embedding_provider.model.provider:
            case 'openai':
                embeddings = OpenAIEmbedder(
                    config=OpenAIEmbedderConfig(
                        api_key=embedding_provider.depService.credentials.to_plain()['api_key'],
                        **embedding_provider.model.graph_embedding_config.model_dump(exclude=('batch',)),
                    )
                )

            case 'gemini':
                embeddings = GeminiEmbedder(
                    batch_size=embedding_provider.depService.model.graph_embedding_config.batch,
                    config=GeminiEmbedderConfig(
                        api_key=embedding_provider.depService.credentials.to_plain()['api_key'],
                        **embedding_provider.model.graph_embedding_config.model_dump(exclude=('base_url','batch')),
                    )
                )
            case _:
                raise BuildFailureError(f'Embeddings provider Mini Service is not supported: provider {llm_client_provider.model.provider} id: {llm_client_provider.miniService_id}')


        match reranker_provider.model.provider:
            case 'openai' | 'gemini':
                config = LLMConfig(
                        api_key=reranker_provider.depService.credentials.to_plain()['api_key'],
                        **reranker_provider.model.graph_config.model_dump(exclude=('reasoning','verbosity','cache'))
                    )
                reranker =  OpenAIRerankerClient(config=config) if reranker_provider.model.provider == 'openai' else GeminiRerankerClient(config=config)
            case _:
                raise BuildFailureError(f'Reranker provider Mini Service is not supported: provider {llm_client_provider.model.provider} id: {llm_client_provider.miniService_id}')


        return llm_client,embeddings,reranker
        
    @property
    def uri(self):
        return f'{self.configService.GRAPHITI_PROTOCOL}://{self.configService.GRAPHITI_HOST}:7687'
    
