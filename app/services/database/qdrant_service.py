from typing import Any
from fastapi import HTTPException
from app.classes.chunk import Chunk
from app.definition._service import BaseService, Service
from app.errors.service_error import BuildFailureError
from app.services.file.file_service import FileService
from app.services.config_service import ConfigService
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import VectorParams, Distance,PointStruct, HnswConfig,SearchParams,Filter, FieldCondition, MatchValue,FilterSelector
from app.services.setting_service import DEFAULT_BUILD_STATE
from app.services.vault_service import VaultService
from app.utils.constant import QdrantConstant
from app.classes.qdrant import SearchParamsModel
from app.utils.tools import RunAsync

@Service()
class QdrantService(BaseService):
    
    def __init__(self,configService:ConfigService,fileService:FileService,vaultService:VaultService):
        super().__init__()
        self.configService = configService
        self.fileService = fileService
        self.vaultService = vaultService
    
    def build(self,build_state:int=DEFAULT_BUILD_STATE):
        try:
            self.client = AsyncQdrantClient(
                url=self.qdrant_url,
                timeout=10,
            )
        except  Exception as e:
            raise BuildFailureError(f"Failed to connect to Qdrant: {e}")
       
    async def create_cache_db(self):
        try:
            return await self.create_collection(QdrantConstant.CACHE_COLLECTION)
        except:
            return False
    
    async def create_collection(self,collection_name:str,metadata:dict[str,Any]=None):
        await self.collection_exists(collection_name,True)
        return await self.client.create_collection(collection_name=collection_name,
                                      vectors_config=VectorParams(512,distance=Distance.COSINE),
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
    
    @RunAsync    
    def upload_points(self,collection_name:str,points:list[Chunk],wait:bool=True):
        temp = []
        for p in points:
            temp.append(
                PointStruct(
                    p.chunk_id,
                    p.vector,
                    p.payload
                )
            )
        points = temp
        return self.client.upload_points(
            collection_name=collection_name,
            points=points,
            wait=wait,
            batch_size=64,
            parallel=2,
            max_retries=3
        )   
    
    async def search(self,query_vector:list[float],collection_name:str,filter:Filter=None,searchParamsModel:SearchParamsModel=None,score_threshold:float=None, top_k:int=5):
        """Search the vector database for similar vectors."""
        
        if searchParamsModel != None:
            searchParamsModel = searchParamsModel.to_qdrant()

        results = await self.client.query_points(
            collection_name=collection_name,
            query_vector=query_vector,
            with_payload=True,
            limit=top_k,
            query_filter=filter,
            score_threshold=score_threshold,
            search_params=searchParamsModel
        )
        contexts = []
        sources = []

        for r in results:
            
            payload = getattr(r, 'payload', {})
            text = payload.get("text","")
            source = payload.get("source","")
            if text:
                sources.append(source)
                contexts.append(text)

        return contexts, sources

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.configService.QDRANT_HOST}:6333"
    
    @property
    def dimension(self) -> int:
        return int(self.configService.getenv("QDRANT_EMBEDDING_DIMENSION",default=512))