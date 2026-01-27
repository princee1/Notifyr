from fastapi import APIRouter, Depends
from app.container import Get
from app.services.database.memcached_service import MemCachedService
from app.services.database.neo4j_service import Neo4JService
from app.services.database.redis_service import RedisService

prefix='/k-graph'


def KnowledgeGraphDBRouter(depends:list=None):
    if depends == None:
        depends =[]

    memcachedService= Get(MemCachedService)
    redisService = Get(RedisService)
    neo4jService = Get(Neo4JService)

    
    async def on_startup():
        await neo4jService.init_database()
    
    async def on_shutdown():
        await neo4jService.close()
    

    router = APIRouter(prefix=prefix,on_startup=[on_startup],on_shutdown=[on_shutdown])

    return router