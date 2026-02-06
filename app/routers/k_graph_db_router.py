from fastapi import APIRouter, Depends
from app.container import Get
from app.services.database.memcached_service import MemCachedService
from app.services.database.bolt_service import BoltService
from app.services.database.redis_service import RedisService

prefix='/k-graph'


def KnowledgeGraphDBRouter(depends:list=None):
    if depends == None:
        depends =[]

    memcachedService= Get(MemCachedService)
    redisService = Get(RedisService)
    boltService = Get(BoltService)

    
    async def on_startup():
        await boltService.init_database()
    
    async def on_shutdown():
        await boltService.close()
    

    router = APIRouter(prefix=prefix,on_startup=[on_startup],on_shutdown=[on_shutdown])

    return router