from datetime import datetime
from typing import Any, Dict, Iterator, Type
from typing_extensions import Literal
from app.classes.chunk import Chunk
from app.definition._service import DEFAULT_BUILD_STATE, BaseService, LinkDep, Service, ServiceStatus
from app.errors.service_error import BuildError, BuildFailureError, BuildNotImplementedError
from app.services.agent.llm_provider_service import LLMProviderMiniService, LLMProviderService
from app.services.config_service import ConfigService, UvicornWorkerService
from app.services.custom_service import CustomService
from app.services.database.base_db_service import TempCredentialsDatabaseService
from app.services.database.mongoose_service import MongooseService
from app.services.database.redis_service import RedisService
from app.services.file.file_service import FileService
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
from graphiti_core.search.search_config import DEFAULT_SEARCH_LIMIT,SearchConfig,SearchResults
from graphiti_core.search.search_filters import SearchFilters
from graphiti_core.nodes import Node
from graphiti_core.driver.neo4j_driver import Neo4jDriver


from app.utils.helper import uuid_v1_mc
from app.utils.constant import GraphitiConstant, LLMProviderConstant, VaultConstant, VaultTTLSyncConstant
import app.prompt.graphiti_prompt as graphiti_prompt
from app.utils.globals import APP_MODE, ApplicationMode


CLIENT_MAP:Dict[LLMProviderConstant.LLMProvider,Type[LLMClient]] = {
    'groq':GroqClient,
    'gemini':GeminiClient,
    'openai':OpenAIClient,
    'anthropic':AnthropicClient,
    'deepseek':OpenAIGenericClient
}

GRAPHITI_BUILD_STATE = 421

@Service(
    links=[LinkDep(service=LLMProviderService,to_build=True,build_state=GRAPHITI_BUILD_STATE)]
)
class GraphitiService(TempCredentialsDatabaseService):
      
    def __init__(self,configService:ConfigService,redisService:RedisService,uvicornWorkerService:UvicornWorkerService,vaultService:VaultService,mongooseService:MongooseService,llmProviderService:LLMProviderService,customService:CustomService,fileService:FileService):
        super().__init__(configService,fileService,vaultService,VaultTTLSyncConstant.VAULT_TOKEN_TTL)
        self.uvicornWorkerService = uvicornWorkerService
        self.mongooseService = mongooseService
        self.llmProviderService = llmProviderService
        self.customService = customService
        self.redisService = redisService
    
    def verify_dependency(self):
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
    
    def build(self, build_state = DEFAULT_BUILD_STATE):
        try:
            client = None
            self.creds = self.vaultService.database_engine.generate_credentials(role='neo4j')
            if build_state == DEFAULT_BUILD_STATE:
                self.client = AsyncGraphDatabase().driver(self.uri,auth=(self.db_user,self.db_password))
                client = GraphDatabase.driver(self.uri,auth=(self.db_user,self.db_password),user_agent=self.uvicornWorkerService.INSTANCE_ID)
                client.verify_connectivity()
                client.verify_authentication()
            
            if build_state == DEFAULT_BUILD_STATE and APP_MODE == ApplicationMode.agentic:
                super().build(build_state)

            providers = self._setup_llm_provider()
            llm_client,embedding,cross_encoder = self._initialize_graphiti_llm(*providers)
            self.graphiti = Graphiti(graph_driver=Neo4jDriver(
                self.uri,
                self.db_user,
                self.db_password,
                GraphitiConstant.DATABASE_NAME
            ),llm_client=llm_client,embedder=embedding,cross_encoder=cross_encoder,max_coroutines=self.configService.GRAPHITI_MAX_COROUTINES)

        except BuildError as e:
            raise e
        except Exception as e:
            raise BuildFailureError(str(e))
        finally:
            if client != None:
                client.close()

    async def close(self):
        await self.graphiti.close()
        await self.client.close()

    async def search(self,query:str,group_type:Literal['domain','contact'],groups_ids:list[str]=[],center_node:str=None,edges:list[str]=[],entities:list[str]=[],config:SearchConfig=None):
        edges = self.customService.to_edge(edges).keys() or None
        entities = self.customService.to_entities(entities).keys() or None

        filtered_group_ids = []
        for grp in groups_ids:
            grp = f"{GraphitiConstant.DOMAIN_PREFIX if group_type =='domain' else GraphitiConstant.CONTACT_PREFIX}{grp}"
            filtered_group_ids.append(grp)

        search_filter = SearchFilters(
            edge_types=edges,
            nodes=entities,
        )

        result = await self.graphiti.search_(
            query=query,
            group_ids=filtered_group_ids,
            search_filter=search_filter,
            config=config,
            center_node_uuid=center_node
        )
        return result
    
    async def build_communities(self):
        await self.graphiti.build_communities()

    ##########################################################################
    #######################                             ######################
    #######################                             ######################
    ##########################################################################

    async def add_chunk_episode(self,chunk:Chunk,instruction:str=None,entities:list[str]=None,edges:list[str]=None):
        name = f"{chunk.payload['document_name']} - {chunk.payload['chunk_id']} - {chunk.payload['title']}"
        source = chunk.payload['source']

        description = description or graphiti_prompt.CHUNK_DESCRIPTION_PROMPT(
            chunk.payload['document_name'],
            chunk.category,
            chunk.payload['section'] or '',
            chunk.payload['title'] or '',
            chunk.payload['topics'] or [],
            chunk.payload['keywords'] or [],
            chunk.payload['most_common'] or [],
            chunk.lang,
        )

        domain = chunk.category
        body = f"""
        text: {chunk.payload['text']}
        -----
        Metadata:
        Page: {chunk.payload['page']}
        Document Id: {chunk.payload['document_id']}
        Density: {chunk.payload['density']}
        Language: {chunk.lang}
        """
        uuid = f"{chunk.payload['document_id']}@{uuid_v1_mc()}"

        return await self.add_content_episode(
            name,
            body,
            source,
            description,
            instruction,
            domain,
            entities,
            edges,
            uuid
        )

    async def add_content_episode(self,name:str,body:dict|str,source:str,description:str,instruction:str=None,domain:str=None,entities:list[str]=None,edges:list[str]=None,uuid:str|None=None):
        
        if not isinstance(body,dict) or not isinstance(body,str):
            raise ValueError('Content is either a dict or a str')

        episode_type = EpisodeType.json if isinstance(body,dict) else EpisodeType.text

        entities = self.customService.to_entities(entities) or None
        edges = self.customService.to_edge(edges) or None
        edge_map = None
        if edges:
            edge_map = self.customService.to_edge_map(edges,entities) or None
        
        domain = f'{GraphitiConstant.DOMAIN_PREFIX}{domain}'

        result = await self.graphiti.add_episode(
            name=name,
            episode_body=body,
            source_description=description,
            reference_time=datetime.now(),
            source=episode_type,
            custom_extraction_instructions=instruction,
            group_id=domain,
            edge_type_map=edge_map,
            edge_types=edges,
            entity_types=entities,
            saga=source,
            #update_communities=True,
            uuid=uuid,
        )

        return result

    async def add_message_episode(self,subject:str,description:str,message:Any,contact_id:str):
        contact_id=f'{GraphitiConstant.CONTACT_PREFIX}{contact_id}'

        description = graphiti_prompt.CONVERSATION_DESCRIPTION_PROMPT(
            description,
            contact_id,
            ...
        )
        episode_name = f"{subject} - {contact_id}"
        
        result = await self.graphiti.add_episode(
            name=episode_name,
            episode_body=message,
            source_description=description,
            source=EpisodeType.message,
            custom_extraction_instructions=graphiti_prompt.CONVERSATION_EXTRACTION_PROMPT(
                subject=subject
            ),
            reference_time=datetime.now(),
            group_id=contact_id,
            saga=subject
        )

        return result

    ##########################################################################
    #######################                             ######################
    #######################                             ######################
    ##########################################################################

    async def get_domain_nodes(self, domain: str, domain_type: Literal['domain', 'contact']) -> list[dict]:
        formatted_domain_id = f'{GraphitiConstant.DOMAIN_PREFIX if domain_type == "domain" else GraphitiConstant.CONTACT_PREFIX}{domain}'
        
        async with self.client.session(database=GraphitiConstant.DATABASE_NAME) as session:
            result = await session.run(
                """
                MATCH (n:Entity|Episode|Community) 
                WHERE n.group_id = $group_id
                RETURN n
                """,
                group_id=formatted_domain_id
            )
            nodes = []
            async for record in result:
                nodes.append(dict(record['n']))
            return nodes

    async def get_document_nodes(self, document_id: str) -> list[dict]:
        """
        Retrieve all nodes where the UUID starts with a specific prefix.
        
        Returns:
            List of node dictionaries with matching UUIDs
        """
        async with self.client.session(database=GraphitiConstant.DATABASE_NAME) as session:
            result = await session.run(
                """
                MATCH (n:Entity|Episode|Community) 
                WHERE STARTS_WITH(n.uuid, $prefix)
                RETURN n
                """,
                prefix=document_id
            )
            nodes = []
            async for record in result:
                nodes.append(dict(record['n']))
            return nodes

    async def delete_document(self, document_id: str) -> int:
        """
        Delete all nodes where the UUID starts with a specific prefix.
                    
        Returns:
            Number of nodes deleted
        """
        async with self.client.session(database=GraphitiConstant.DATABASE_NAME) as session:
            result = await session.run(
                """
                MATCH (n:Entity|Episode|Community) 
                WHERE STARTS_WITH(n.uuid, $prefix)
                DETACH DELETE n
                RETURN count(n) as deleted_count
                """,
                prefix=document_id
            )
            record = await result.single()
            return record['deleted_count'] if record else 0

    async def delete_domain(self,domain:str,domain_type: Literal['domain', 'contact'],batch:int=100):
        formatted_domain_id = f'{GraphitiConstant.DOMAIN_PREFIX if domain_type == "domain" else GraphitiConstant.CONTACT_PREFIX}{domain}'

        await Node.delete_by_group_id(
            self.client,
            group_id=formatted_domain_id,
            batch_size=batch
        )

    async def delete_node_by(self,uuid:str):
        await Node.delete_by_uuids(
            batch_size=1,
            uuids=[uuid]
        )
    
    async def get_node_by(self,uuid:str):
        ...
    
    ##########################################################################
    #######################                             ######################
    #######################                             ######################
    ##########################################################################

    async def init_database(self,):
        try:
            await self.graphiti.build_indices_and_constraints()
        except:
            ...

    def _setup_llm_provider(self):

        provider_config = self.llmProviderService.graphiti_config

        llm_client_provider = provider_config.get('client', None)
        embedding_provider = provider_config.get('embedding', None)
        reranker_provider = provider_config.get('reranker', None)

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
    
