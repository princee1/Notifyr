from app.definition._tool import Tool,ContextPipelineTool
from app.models.agents_model import CacheToolModel
from app.services import ConfigService
from app.services import QdrantService
from app.services import MemCachedService

class CacheTool(ContextPipelineTool):
    
    def __init__(self,configService:ConfigService,qdrantService:QdrantService,config:CacheToolModel):
        self.configService = configService
        self.qdrantService = qdrantService

    async def __call__(self,query:str)->str:
        ...