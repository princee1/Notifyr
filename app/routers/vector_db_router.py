from fastapi import APIRouter
from app.container import Get
from app.services.database.memcached_service import MemCachedService
from app.services.database.qdrant_service import QdrantService
from app.services.database.redis_service import RedisService


def VectorDBRouter(depends:list=None):
    prefix=''
    if depends == None:
        depends =[]

    qdrantService = Get(QdrantService)
    memcachedService= Get(MemCachedService)
    redisService = Get(RedisService)

    async def on_startup():
        ...
    
    async def on_shutdown():
        ...
    

    router = APIRouter(prefix,on_startup=[on_startup],on_shutdown=[on_shutdown])



    return router