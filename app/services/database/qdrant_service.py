from typing import Any, Dict, List, Literal, Tuple
from fastapi import HTTPException
from app.classes.chunk import CONTEXT_KEYS, ChunkWrapper, ChunkContext
from app.classes.embeddings import EmbeddingUsage, EmbeddingWrapper
from app.definition._service import BaseService, LinkDep, Service
from app.errors.service_error import BuildFailureError
from app.services.agent.llm_provider_service import LLMProviderService
from app.services.file.file_service import FileService
from app.services.config_service import ConfigService
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Record, ScoredPoint, VectorParams, Distance,PointStruct,Filter, FieldCondition, MatchValue,FilterSelector, MatchText, MatchAny, MinShould, MatchPhrase, MatchTextAny
from app.services.setting_service import DEFAULT_BUILD_STATE
from app.services.vault_service import VaultService
from app.classes.qdrant import QdrantCollectionDoesNotExistError, QdrantFilterModel, QdrantSearchParamsModel, QdrantChunkFilterCondition, TextFieldMatch
from app.classes.qdrant import LIST_FIELDS,LITERAL_FIELDS,FLEXIBLE_TEXT_FIELDS
from app.utils.helper import slice_dict
from app.utils.tools import RunAsync
from app.utils.globals import APP_MODE,ApplicationMode

QDRANT_BUILD_STATE = 543
ExportContext = Literal['list','dict']

LLAMA_EMBEDDING_KEYS = ('model','timeout','max_retries','api_base','api_version')

@Service(
    links=[LinkDep(service=LLMProviderService,to_build=True,build_state=QDRANT_BUILD_STATE)]
)
class QdrantService(BaseService):
    
    def __init__(self,configService:ConfigService,fileService:FileService,vaultService:VaultService,llmProviderService:LLMProviderService):
        super().__init__()
        self.configService = configService
        self.fileService = fileService
        self.vaultService = vaultService
        self.llmProviderService = llmProviderService
    
    def verify_dependency(self):
        if self.llmProviderService.vector_config.get('embedding',None) == None:
            raise BuildFailureError('Qdrant Vector config is not specified in the configuration')

    def build(self,build_state:int=DEFAULT_BUILD_STATE):

        if build_state == DEFAULT_BUILD_STATE:
            try:
                    self.client = AsyncQdrantClient(
                        url=self.qdrant_url,
                        timeout=10,
                    )
            except  Exception as e:
                raise BuildFailureError(f"Failed to connect to Qdrant: {e}")

            if APP_MODE == ApplicationMode.arq:
                self._create_embedding_object()
            
            if APP_MODE == ApplicationMode.agentic:
                self._create_llm_client()

    async def close(self):
        if self.client:
            await self.client.close()

    ##################################################################################################################
    #######################################                                         ##################################
    ##################################################################################################################

    def _create_embedding_object(self):
        from llama_index.embeddings.openai import OpenAIEmbedding,OpenAIEmbeddingMode
        if False:
            from llama_index.embeddings.gemini import GeminiEmbedding
     
        if not self.embedding_id:
            raise BuildFailureError("No embedding provider configured in vector_embedding_config")
        
        embedding_provider = self.llmProviderService.MiniServiceStore.get(self.embedding_id)
        self.vector_config = embedding_provider.model.vector_embedding_config
        api_key = embedding_provider.depService.credentials.to_plain()

        self.embed_provider = embedding_provider.model.provider

        match self.embed_provider:
            case 'gemini':
                raise BuildFailureError('Gemini not supported')
                embedding = GeminiEmbedding(
                    api_key=api_key,
                    model_name=vector_config.model,
                    **vector_config.model_dump(include=('timeout','max_retries','api_base'))
                )
                self.embedding_parse = embedding
                self.embedding_search = embedding
            
            case 'openai':
                self.embedding_parse = OpenAIEmbedding(
                    api_key=api_key,
                    dimensions=self.DEFAULT_DIMENSION,
                    mode=OpenAIEmbeddingMode.TEXT_SEARCH_MODE,
                    **self.vector_config.model_dump(include=LLAMA_EMBEDDING_KEYS),
                )
                self.embedding_search = OpenAIEmbedding(
                    api_key=api_key,
                    dimensions=self.DEFAULT_DIMENSION,
                    mode=OpenAIEmbeddingMode.SIMILARITY_MODE,
                    **self.vector_config.model_dump(include=LLAMA_EMBEDDING_KEYS ),
                )
            case _:
                raise BuildFailureError(f"Unsupported embedding provider: {embedding_provider.model.provider}")

    def _create_llm_client(self):
        from openai import AsyncOpenAI
        from openai.types import CreateEmbeddingResponse
        
        if not self.embedding_id:
            raise BuildFailureError("No embedding provider configured in vector_embedding_config")
        
        embedding_provider = self.llmProviderService.MiniServiceStore.get(self.embedding_id)
        self.vector_config = embedding_provider.model.vector_embedding_config
        self.embed_provider = embedding_provider.model.provider

        match self.embed_provider:
            case 'gemini':
                raise BuildFailureError('Gemini not supported')
                
            case 'openai':
                self.embedding_search = AsyncOpenAI(api_key=embedding_provider.depService.credentials.to_plain,
                                                    base_url=self.vector_config.api_base,
                                                    timeout=self.vector_config.timeout,
                                                    max_retries=self.vector_config.max_retries).embeddings
            case _:
                raise BuildFailureError(f"Unsupported embedding provider: {embedding_provider.model.provider}")
            
    ##################################################################################################################
    #######################################                                         ##################################
    ##################################################################################################################

    async def create_collection(self,collection_name:str,metadata:dict[str,Any]=None):
        await self.collection_exists(collection_name,True)
        return await self.client.create_collection(collection_name=collection_name,
                                      vectors_config=VectorParams(self.DEFAULT_DIMENSION,distance=Distance.COSINE),
                                      on_disk_payload=True,
                                      metadata=metadata
                                      #hnsw_config=HnswConfig()
                                      )
    
    async def get_collection(self,collection_name:str):
        await  self.collection_exists(collection_name)
        return await self.client.get_collection(collection_name)

    async def get_collections(self):
        return await self.client.get_collections()    
    
    async def collection_exists(self,collection_name:str,reverse:bool|None = False)->bool:
        exist =  await self.client.collection_exists(collection_name)

        if reverse == None:
            return exist 
    
        if not exist and not reverse:
            raise HTTPException(404,f'Collection: {collection_name} does not exists')

        if exist and reverse:
            raise HTTPException(400,f'Collection: {collection_name} already exists')
                
    async def delete_collections(self,collection_name:str):
        await  self.collection_exists(collection_name)
        return self.client.delete_collection(collection_name,8)

    async def clear_collections(self,collection_name:str):
        await  self.collection_exists(collection_name)
        return await self.client.delete(
            collection_name=collection_name,
            points_selector=FilterSelector(
                filter=Filter()
            )
        )

    async def delete_document(self, collection_name: str, document_id: str | None = None, document_name: str | None = None, wait: bool = True):
        """Delete all points in a collection whose payload matches the given document id or document name.

        At least one of `document_id` or `document_name` must be provided. The function builds
        a payload filter and calls Qdrant to remove matching points.
        """
        await self.collection_exists(collection_name)

        if not document_id and not document_name:
            raise HTTPException(status_code=400, detail='document_id or document_name is required')

        must_conditions = []
        if document_id:
            must_conditions.append(FieldCondition(key='document_id', match=MatchValue(value=document_id)))
        if document_name:
            must_conditions.append(FieldCondition(key='document_name', match=MatchValue(value=document_name)))

        payload_filter = Filter(must=must_conditions)

        try:
            # Use the client's delete_points method to remove points matching the filter
            return await self.client.delete(
                collection_name=collection_name,
                points_selector=payload_filter,
                wait=wait
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'Failed to delete points: {e}')
    
    ##################################################################################################################
    #######################################                                         ##################################
    ##################################################################################################################

    @RunAsync    
    def upload_points(self,collection_name:str,chunks:list[ChunkWrapper],wait:bool=True):
        points = []
        for c in chunks:
            points.append(
                PointStruct(
                    c.chunk_id,
                    c.vector,
                    c.payload
                )
            )
        return self.client.upload_points(
            collection_name=collection_name,
            points=points,
            wait=wait,
            batch_size=64,
            parallel=2,
            max_retries=3
        )   
    
    async def search(self,query_vector:list[float],collection_name:str,filter:QdrantFilterModel|Filter=None,search_params:QdrantSearchParamsModel=None,score_threshold:float=None, top_k:int=5,with_vector=True,export:ExportContext='list'):
        """Search the vector database for similar vectors."""
        exist = await self.collection_exists(collection_name,None)
        if not exist:
            raise QdrantCollectionDoesNotExistError(collection_name)
        
        if search_params != None:
            search_params = search_params.to_qdrant()
        
        if filter != None and isinstance(filter,QdrantFilterModel):
            filter = self.to_filter(filter)

        results = await self.client.query_points(
            collection_name=collection_name,
            query_vector=query_vector,
            with_vectors=with_vector,
            with_payload=True,
            limit=top_k,
            query_filter=filter,
            score_threshold=score_threshold,
            search_params=search_params
        )

        return self.to_context(results.points,export)

    async def get_points(self,collection_name:str,point_uuid:str|list[str],with_vector=False,timeout=2,export:ExportContext='list'):
        exist = await self.collection_exists(collection_name,None)
        if not exist:
            raise QdrantCollectionDoesNotExistError(collection_name)

        if isinstance(point_uuid,str):
            point_uuid = [point_uuid]

        points = await self.client.retrieve(
            collection_name=collection_name,
            ids=point_uuid,
            with_payload=True,
            with_vectors=with_vector,
            timeout=timeout
        )
        
        return self.to_context(points,export)
    
    async def embed_query(self,query:str,model:str|None|dict=None,dimension:int=None)->List[float]|Tuple[EmbeddingWrapper,EmbeddingUsage]:
        if APP_MODE == ApplicationMode.arq:
            return await self.embedding_search.aget_query_embedding(
                query
            )
        if APP_MODE == ApplicationMode.agentic:
            if isinstance(model,dict):
                model = model.get(self.embed_provider,None)
            
            model = model or self.vector_config.model
            dimension = dimension or self.DEFAULT_DIMENSION

            match self.embed_provider:
                case 'openai':
                    resp = await self.embedding_search.create(query,model=model,dimensions=dimension)
                    embedding = EmbeddingWrapper(None,resp.data[0],norm=None,)
                    usage = EmbeddingUsage(resp.usage.prompt_tokens,resp.usage.total_tokens,model,self.embed_provider)
                case 'gemini':
                    ...
                
            return embedding,usage
    
    def to_context(self,results:List[Record|ScoredPoint],export:ExportContext='list')->List[ChunkContext]|Dict[str,ChunkContext]:
        if export == 'list':
            contexts = []
        else:
            context = {}
        for point in results:
            payload = point.payload
            slice_dict(payload,CONTEXT_KEYS,'include')
            if hasattr(point,'score'):
                similarity = point.score
            else:
                similarity = None
            context = ChunkContext(chunk_id=point.id,**payload,vector=point.vector or None,similarity=similarity)
            if export == 'list':
                contexts.append(context)
            else:
                contexts[context['chunk_id']] = context
            
        return contexts

    def to_filter(self, filter_model: QdrantFilterModel) -> Filter | None:
        if filter_model == None:
            return None
        
        return Filter(
            min_should=MinShould(condition_to_field_conditions(filter_model.should),filter_model.min_should) if filter_model.should else None,
            must_not=condition_to_field_conditions(filter_model.must_not),
            must=condition_to_field_conditions(filter_model.must),
        )
    
    ##################################################################################################################
    #######################################                                         ##################################
    ##################################################################################################################

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.configService.QDRANT_HOST}:6333"

    @property
    def embedding_id(self)->str:
        return self.llmProviderService.vector_config.get('embedding',None)

    @property
    def DEFAULT_DIMENSION(self) -> int:
        return int(self.configService.getenv("QDRANT_EMBEDDING_DIMENSION",default=512))


def get_text_match(text_field_match: TextFieldMatch):
    """Convert TextFieldMatch to appropriate Qdrant match object based on strategy."""
    value = text_field_match.value
    strategy = text_field_match.strategy
    
    if strategy == 'phrase':
        return MatchPhrase(phrase=value)
    elif strategy == 'token':
        return MatchTextAny(text_any=value)
     
def condition_to_field_conditions(condition: QdrantChunkFilterCondition) -> list[FieldCondition]:
    """Convert a ChunkFilterCondition to list of FieldConditions."""
    field_conditions = []
    for field,value in condition.model_dump():
        if field in LITERAL_FIELDS:
            for v in value:
                field_conditions.append(FieldCondition(key=field,match=MatchValue(value=v)))

        if field in FLEXIBLE_TEXT_FIELDS:
            match_obj = get_text_match(value)
            field_conditions.append(FieldCondition(key=field,match=match_obj))

        if field in LIST_FIELDS:
            if value is not None and len(value) > 0:
                field_conditions.append(FieldCondition(key=field,match=MatchAny(any=value)))

    return field_conditions