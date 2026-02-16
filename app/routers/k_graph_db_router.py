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
    graphitiService = Get(GraphitiService)

    async def on_startup():
        await graphitiService.init_database()
    
    async def on_shutdown():
        await graphitiService.close()
    
    router = APIRouter(prefix=prefix,on_startup=[on_startup],on_shutdown=[on_shutdown])

    @router.get('/node/{uuid}/')
    async def get_node(self,uuid:str):
        ...

    @router.delete('/node/{uuid}/')
    async def delete_node(self,uuid:str):
        ...

    ########################         #######################
    ########################         #######################

    @router.get('/document/{document_id}/')
    async def get_document_graph(self,document_id:str):
        ...

    @router.delete('/document/{document_id}/')
    async def delete_document(self,document_id:str):
        ...

    ########################         #######################
    ########################         #######################

    @router.get('/domain/{domain}/')
    async def get_domain_graph(self,domain:str):
        ...
    
    @router.delete('/domain/{domain}/')
    async def delete_domain(self,domain:str):
        ...
    
    return router