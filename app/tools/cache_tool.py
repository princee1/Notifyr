from pydantic import BaseModel, Field
from langchain.agents.middleware import after_agent, before_agent,before_model,Runtime
from app.definition._agent import NotifyrAgentState, NotifyrContext
from app.definition._tool import RetrievalTool, ToolContextFactory, ToolRuntime
from app.models.odm.agents_model import AgentModel
from app.models.odm.tools_model import CacheToolModel
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
    
    def __init__(self,configService:ConfigService,redisService:RedisService,qdrantService:QdrantService,config:CacheToolModel,temperature:int):
        super().__init__(config,)
        self.configService = configService
        self.redisService = redisService
        self.qdrantService = qdrantService
        self.temperature = temperature


    async def __call__(self,runtime:ToolRuntime,mode:CacheMode,query:str,response:str=None)->str:
        try:
            async with ToolContextFactory() as factory:
                match mode:
                    case 'cache':
                        return await self.cache()
                    case 'invalidate': 
                        return await self.invalidate()
                    case 'lookup':
                        return self.lookup()
                    case _:
                        ...
        except:
            ...

    async def lookup(self,query:str):
        ...
    
    async def cache(self,query:str,response:str):
        ...
    
    async def invalidate(self,query:str):
        ...


def DirectCachePromptFactory(agentModel:AgentModel,toolModel:CacheToolModel,redisService:RedisService,qdrantService:QdrantService, as_list=False):

    @before_agent
    async def before_cache_prompt(state: NotifyrAgentState, runtime: Runtime[NotifyrContext]):
        ...
    
    @after_agent
    async def after_cache_prompt(state:NotifyrAgentState,runtime:Runtime[NotifyrContext]):
        ...

    return before_cache_prompt,after_cache_prompt if as_list else [before_cache_prompt,after_cache_prompt]