from fastapi import APIRouter, Depends, HTTPException, Request, Response,status
from app.container import Get
from app.definition._router import lock_service_wrapper
from app.models.graphiti_model import GraphitiSearchModel
from app.services.database.memcached_service import MemCachedService
from app.services.database.graphiti_service import GraphitiService
from app.services.database.redis_service import RedisService
from app.services.worker.arq_service import ArqIngestTaskService

prefix='/k-graph'

def KnowledgeGraphDBRouter(depends:list=None):
    if depends == None:
        depends =[]

    memcachedService= Get(MemCachedService)
    arqService = Get(ArqIngestTaskService)
    graphitiService = Get(GraphitiService)

    async def on_startup():
        await graphitiService.init_database()
    
    async def on_shutdown():
        await graphitiService.close()
    
    router = APIRouter(prefix=prefix,on_startup=[on_startup],on_shutdown=[on_shutdown])


    ########################         #######################
    ########################         #######################

    @router.get('/document/{document_id}/',status_code=status.HTTP_200_OK)
    @lock_service_wrapper(GraphitiService)
    async def get_document_graph(response:Response,request:Request,document_id:str):
        return await graphitiService.get_document_nodes(
            document_id=document_id
        )

    @router.delete('/document/{document_id}/',status_code=status.HTTP_200_OK)
    @lock_service_wrapper(GraphitiService)
    async def delete_document(response:Response,request:Request,document_id:str):
        count=await graphitiService.delete_document(
            document_id
        )

        return count > 0

    ########################         #######################
    ########################         #######################

    @router.get('/domain/{domain}/',status_code=status.HTTP_200_OK)
    @lock_service_wrapper(GraphitiService)
    async def get_domain_graph(response:Response,request:Request,domain:str):
        return await graphitiService.get_domain_nodes(
            domain=domain,
            domain_type='domain'
        )
    
    @router.delete('/domain/{domain}/',status_code=status.HTTP_200_OK)
    @lock_service_wrapper(GraphitiService)
    async def delete_domain(response:Response,request:Request,domain:str,):
        
        nodes = await graphitiService.get_domain_nodes(
            domain=domain,
            domain_type='domain'
        )
        
        if not nodes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Domain: {domain} does not have nodes '
            )

        await graphitiService.delete_domain(
            domain,
            domain_type='domain',
            batch=100
        )
    
    ########################         #######################
    ########################         #######################

    @router.post('/playground/')
    @lock_service_wrapper(GraphitiService)
    async def graphiti_playground(response:Response,request:Request,search:GraphitiSearchModel):
        await graphitiService.search(
            "",
            group_type='domain',

        )

    return router