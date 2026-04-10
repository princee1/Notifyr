from typing import Dict, Literal
from fastapi import APIRouter, BackgroundTasks, Query, Request, Response, status, Body,HTTPException
from app.classes.cost_definition import InsufficientCreditsError, InvalidPurchaseRequestError
from app.classes.embeddings import EmbeddingUsage
from app.container import Get
from app.cost.token_cost import TokenCost
from app.definition._router import HandlerDetails, exception_handler, lock_service_wrapper
from app.models.vector_model import QdrantEmbedRequestModel
from app.services.cost_service import CostService
from app.services.database.memcached_service import MemCachedService
from app.services.database.qdrant_service import QdrantService
from app.services.database.redis_service import RedisService
from app.services.worker.arq_service import ArqIngestTaskService
from app.utils.constant import AgenticConstant, CostConstant

prefix=AgenticConstant.VECTOR_ROUTER('')

def VectorDBRouter(depends:list=None):
    if depends == None:
        depends =[]

    qdrantService = Get(QdrantService)
    costService = Get(CostService)
    memcachedService= Get(MemCachedService)
    arqService = Get(ArqIngestTaskService)

    async def on_startup():
        ...
    
    async def on_shutdown():
        ...
    
    router = APIRouter(prefix=prefix,on_startup=[on_startup],on_shutdown=[on_shutdown])

    @router.post('/',status_code=status.HTTP_201_CREATED)
    @lock_service_wrapper(QdrantService)
    async def create_collection(request:Request,response:Response,collection:Dict = Body()):
        if not isinstance(collection,dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Bad collection format'
            )
        if not await qdrantService.create_collection(
            **collection
        ):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not create the collection"
            )
        return 

    @router.get('/s/{collection_name}',status_code=status.HTTP_200_OK)
    @lock_service_wrapper(QdrantService)
    async def get_collection(request:Request,response:Response,collection_name:str):
        collection = await qdrantService.get_collection(
            collection_name
            )
        return collection.model_dump()
       
    @router.delete('/',status_code=status.HTTP_200_OK)
    @lock_service_wrapper(QdrantService)
    async def delete_collection(request:Request,response:Response,collection_name:str,mode:Literal['hard','soft']=Query('soft')):
        if mode =='hard':
            res = await qdrantService.delete_collections(collection_name)
            if not res:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f'Could not delete the collection'
                )
        else:
            res = await qdrantService.clear_collections(collection_name)
            return res.model_dump()

    @router.get('/',status_code=status.HTTP_200_OK)
    @lock_service_wrapper(QdrantService)
    async def get_all_collection(request:Request,response:Response,collection_name:str):
        collections = await qdrantService.get_collections()
        return collections.model_dump()

    @router.delete('/docs/{collection_name}/{job_id}',status_code=status.HTTP_200_OK)
    @lock_service_wrapper(QdrantService)
    async def delete_document(job_id:str,request:Request,response:Response,collection_name:str):
        document_name = job_id
        res = await qdrantService.delete_document(
            document_name=document_name,
            collection_name=collection_name,
        )
        return res.model_dump()
    
    @router.post('/embed/',status_code=status.HTTP_200_OK)
    @lock_service_wrapper(QdrantService)
    @exception_handler({InvalidPurchaseRequestError:HandlerDetails(400),InsufficientCreditsError:HandlerDetails(402)})
    async def embed_query(request:Request,response:Response,backgroundTasks:BackgroundTasks,query:QdrantEmbedRequestModel):
        await costService.check_enough_credits(CostConstant.TOKEN_CREDIT,8192*2)

        embedding,usage = await qdrantService.embed_query(
            query=query.query
        )

        async def purchase_embed_token(usage:EmbeddingUsage):
            cost = TokenCost(query.request_id,query.issuer)
            cost.purchase(usage.model,usage.provider,...,'input','Embedding Query',usage.prompt_tokens)
            cost.purchase(usage.model,usage.provider,...,'output','Embedding Query',usage.embed_tokens)
            await costService.deduct_credits(CostConstant.TOKEN_CREDIT,cost.generate_bill())

        backgroundTasks.add_task(purchase_embed_token,usage)
        return embedding.export('json')

    return router