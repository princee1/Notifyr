from fastapi import APIRouter, Depends
from app.container import Get
from app.services.agent.agent_service import AgentService
from app.services.config_service import ConfigService
from app.services.database.memcached_service import MemCachedService
from app.services.database.redis_service import RedisService


def PromptPlaygroundRouter(depends:list=None):
    prefix=''
    if depends == None:
        depends =[]

    memcachedService= Get(MemCachedService)
    redisService = Get(RedisService)
    agentService = Get(AgentService)
    configService = Get(ConfigService)

    

    async def on_startup():
        ...
    
    async def on_shutdown():
        ...
    

    router = APIRouter(prefix=prefix,on_startup=[on_startup],on_shutdown=[on_shutdown])

    return router