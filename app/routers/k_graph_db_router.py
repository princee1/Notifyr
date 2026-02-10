from fastapi import APIRouter, Depends
from app.container import Get
from app.services.database.memcached_service import MemCachedService
from app.services.database.graphiti_service import GraphitiService
from app.services.database.redis_service import RedisService

prefix='/k-graph'


def KnowledgeGraphDBRouter(depends:list=None):
    if depends == None:
        depends =[]

    memcachedService= Get(MemCachedService)
    redisService = Get(RedisService)
    graphitiService = Get(graphitiService)

    
    async def on_startup():
        await graphitiService.init_database()
    
    async def on_shutdown():
        await graphitiService.close()
    

    router = APIRouter(prefix=prefix,on_startup=[on_startup],on_shutdown=[on_shutdown])

    return router