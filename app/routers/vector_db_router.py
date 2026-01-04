from fastapi import APIRouter, Request, Response
from app.container import Get
from app.services.database.memcached_service import MemCachedService
from app.services.database.qdrant_service import QdrantService
from app.services.database.redis_service import RedisService

prefix='vector'


def VectorDBRouter(depends:list=None):
    if depends == None:
        depends =[]

    qdrantService = Get(QdrantService)
    memcachedService= Get(MemCachedService)
    redisService = Get(RedisService)

    async def on_startup():
        ...
    
    async def on_shutdown():
        ...
    

    router = APIRouter(prefix=prefix,on_startup=[on_startup],on_shutdown=[on_shutdown])


    @router.post('/')
    async def create_collection():
        ...

    @router.get('/')
    async def get_collection():
        ...

    @router.delete('/')
    async def delete_collection():
        ...

    async def get_all_collection():
        ...

    @router.delete('/docs/{job_id}')
    async def delete_document(request:Request,response:Response):
        ...


    return router