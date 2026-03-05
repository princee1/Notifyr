from fastapi import APIRouter, Depends, Request, Response
from app.container import Get
from app.definition._router import service_lock_decorator
from app.services.database.memcached_service import MemCachedService
from app.services.database.graphiti_service import GraphitiService
from app.services.database.redis_service import RedisService
from app.services.worker.arq_service import ArqDataTaskService

prefix='/k-graph'

def KnowledgeGraphDBRouter(depends:list=None):
    if depends == None:
        depends =[]

    memcachedService= Get(MemCachedService)
    arqService = Get(ArqDataTaskService)
    graphitiService = Get(GraphitiService)

    async def on_startup():
        await graphitiService.init_database()
    
    async def on_shutdown():
        await graphitiService.close()
    
    router = APIRouter(prefix=prefix,on_startup=[on_startup],on_shutdown=[on_shutdown])


    ########################         #######################
    ########################         #######################

    @router.get('/document/{document_id}/')
    @service_lock_decorator(GraphitiService)
    async def get_document_graph(response:Response,request:Request,document_id:str):
        ...

    @router.delete('/document/{document_id}/')
    @service_lock_decorator(GraphitiService)
    async def delete_document(response:Response,request:Request,document_id:str):
        ...

    ########################         #######################
    ########################         #######################

    @router.get('/domain/{domain}/')
    @service_lock_decorator(GraphitiService)
    async def get_domain_graph(response:Response,request:Request,domain:str):
        ...
    
    @router.delete('/domain/{domain}/')
    @service_lock_decorator(GraphitiService)
    async def delete_domain(response:Response,request:Request,domain:str,):
        ...
    
    ########################         #######################
    ########################         #######################

    @router.post('/playground/')
    @service_lock_decorator(GraphitiService)
    async def graphiti_playground(response:Response,request:Request):
        await graphitiService.search(
            "",
            group_type='domain',

        )

    return router