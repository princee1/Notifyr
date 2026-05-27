from pydantic import BaseModel, Field

from app.definition._tool import RetrievalTool, ToolRuntime
from app.models.tools_model import CacheToolModel
from app.services import ConfigService
from app.services import RedisService
from app.services import QdrantService
from langchain_community.vectorstores import Redis
from typing import Literal, Optional

CacheMode = Literal['lookup','cache','invalidate']
ScopeMode = Literal['general','personal','group']

class CacheArgsSchema(BaseModel):
    """ Input for interacting with the cache"""
    mode: CacheMode = Field()
    scope: ScopeMode
    query:str
    response:Optional[str] = Field(default=None)

class CacheTool(RetrievalTool):
    
    def __init__(self,configService:ConfigService,redisService:RedisService,config:CacheToolModel,qdrantService:QdrantService,store):
        super().__init__(config,)
        self.configService = configService
        self.redisService = redisService
        self.qdrantService = qdrantService
        self.store  = store # NOTE for personal or global without an eviction time

    async def __call__(self,runtime:ToolRuntime,mode:CacheMode,query:str,response:str=None)->str:
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