from app.definition._tool import Tool,ContextPipelineTool
from app.models.tools_model import CacheToolModel
from app.services import ConfigService
from app.services import QdrantService
from app.services.database.redis_service import RedisService

class CacheTool(ContextPipelineTool):
    
    def __init__(self,configService:ConfigService,qdrantService:QdrantService,redisService:RedisService,config:CacheToolModel):
        self.configService = configService
        self.qdrantService = qdrantService
        self.config = config

    async def __call__(self,query:str)->str:
        ...