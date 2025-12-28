from typing import Any
from fastapi import HTTPException
from app.definition._service import BaseService, Service
from app.errors.service_error import BuildFailureError
from app.services.file.file_service import FileService
from app.services.config_service import ConfigService
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import VectorParams, Distance,PointStruct, HnswConfig,SearchParams,Filter
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
        if await self.collection_exists(collection_name):
            raise HTTPException(400,f'Collection already exists')
        return await self.client.create_collection(collection_name=collection_name,
                                      vectors_config=VectorParams(512,distance=Distance.COSINE),
                                      on_disk_payload=True,
                                      metadata=metadata
                                      #hnsw_config=HnswConfig()
                                      )
    
    async def get_collection(self,collection_name:str):
        if not await  self.collection_exists(collection_name):
            raise HTTPException(404,f'Collection does not exists')
        return await self.client.get_collection(collection_name)

    async def update_collection(self,collect_name:str):
        return await self.client.update_collection(
            collection_name=collect_name,
            

        )

    async def get_collections(self):
        return await self.client.get_collections()    
    
    async def collection_exists(self,collection_name:str)->bool:
        return await self.client.collection_exists(collection_name)

    async def delete_collections(self,collection_name:str):
        if not await  self.collection_exists(collection_name):
            raise HTTPException(404,f'Collection does not exists')        
        return self.client.delete_collection(collection_name,8)

    async def clear_collections(self,collection_name:str):
        ...        

    @RunAsync    
    def upload_points(self,collection_name:str,points:list[PointStruct],wait:bool=True):
        return self.client.upload_points(
            collection_name=collection_name,
            points=points,
            wait=wait,
            batch_size=64,
            parallel=2
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