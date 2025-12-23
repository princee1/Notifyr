from app.definition._service import BaseService, Service
from app.errors.service_error import BuildFailureError
from app.services.file.file_service import FileService
from app.services.config_service import ConfigService
from qdrant_client.async_qdrant_client import AsyncQdrantClient
from qdrant_client.models import VectorParams, Distance,PointStruct
from app.services.setting_service import DEFAULT_BUILD_STATE
from app.services.vault_service import VaultService

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
        
    async def collection_exists(self,collection_name:str)->bool:
        return await self.client.collection_exists(collection_name)

    async def upsert_points(self,collection_name:str,ids,vectors,payloads):
        points = [PointStruct(id=id, vector=vector, payload=payload) for id, vector, payload in zip(ids, vectors, payloads)]
        await self.client.upsert(
            collection_name=collection_name,
            points=points
        )   
    
    async def search(self,query_vector,collection_name:str,top_k:int=5):
        """Search the vector database for similar vectors."""
        results = await self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            with_payload=True,
            limit=top_k
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