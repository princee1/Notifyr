from typing import Dict, Literal
from fastapi import APIRouter, Query, Request, Response, status, Body,HTTPException
from app.container import Get
from app.services.database.memcached_service import MemCachedService
from app.services.database.qdrant_service import QdrantService
from app.services.database.redis_service import RedisService
from app.services.worker.arq_service import ArqDataTaskService

prefix='/vector'

def VectorDBRouter(depends:list=None):
    if depends == None:
        depends =[]

    qdrantService = Get(QdrantService)
    memcachedService= Get(MemCachedService)
    arqService = Get(ArqDataTaskService)

    async def on_startup():
        ...
    
    async def on_shutdown():
        ...
    
    router = APIRouter(prefix=prefix,on_startup=[on_startup],on_shutdown=[on_shutdown])

    @router.post('/',status_code=status.HTTP_201_CREATED)
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

    @router.get('/{collection_name}',status_code=status.HTTP_200_OK)
    async def get_collection(collection_name:str,request:Request,response:Response):
        collection = await qdrantService.get_collection(
            collection_name
            )
        return collection.model_dump()
       
    @router.delete('/',status_code=status.HTTP_200_OK)
    async def delete_collection(collection_name:str,request:Request,response:Response,mode:Literal['hard','soft']=Query('soft')):
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

    @router.get('/all/',status_code=status.HTTP_200_OK)
    async def get_all_collection(collection_name:str,request:Request,response:Response):
        collections = await qdrantService.get_collections()
        return collections.model_dump()

    @router.delete('/docs/{collection_name}/{job_id}',status_code=status.HTTP_200_OK)
    async def delete_document(collection_name:str,job_id:str,request:Request,response:Response):
        document_name = job_id
        res = await qdrantService.delete_document(
            document_name=document_name,
            collection_name=collection_name,
        )
        return res.model_dump()

    return router