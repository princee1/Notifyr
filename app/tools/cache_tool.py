from app.definition._tool import ContextPipelineTool
from app.models.tools_model import CacheToolModel
from app.services import ConfigService
from app.services import RedisService

class CacheTool(ContextPipelineTool):
    
    def __init__(self,configService:ConfigService,redisService:RedisService,config:CacheToolModel):
        self.configService = configService
        self.redisService = redisService
        self.config = config

    async def __call__(self,query:str)->str:
        ...