from app.definition._tool import ContextPipelineTool
from app.models.tools_model import CacheToolModel
from app.services import ConfigService
from app.services import RedisService
from langchain_community.vectorstores import Redis
from typing import Literal

CacheMode = Literal['lookup','cache','invalidate']

class CacheTool(ContextPipelineTool):
    
    def __init__(self,configService:ConfigService,redisService:RedisService,config:CacheToolModel):
        self.configService = configService
        self.redisService = redisService
        self.config = config

    async def __call__(self,mode:CacheMode,query:str,response:str=None)->str:
        match mode:
            case 'cache':
                return await self.cache()
            case 'invalidate': 
                return await self.invalidate()
            case 'lookup':
                return self.lookup()
            case _:
                ...

    async def lookup(self,query:str):
        ...
    
    async def cache(self,query:str,response:str):
        ...
    
    async def invalidate(self,query:str):
        ...