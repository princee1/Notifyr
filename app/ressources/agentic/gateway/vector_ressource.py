from typing import Annotated
from fastapi import Depends, Request, Response, status
from app.classes.auth_permission import AuthPermission
from app.container import InjectInMethod
from app.cost.ingest_cost import DeleteDocumentIngestCost
from app.decorators.handlers import AgenticHandler, ArqHandler, AsyncIOHandler, CostHandler, DataIngestHandler, ProxyRestGatewayHandler, RedisHandler, ServiceAvailabilityHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.permissions import JWTRouteHTTPPermission
from app.decorators.pipes import DeleteDocumentIngestUpdate, update_status_upon_no_metadata_pipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, Throttle, UseGuard, UseHandler, UseInterceptor, UseLimiter, UsePermission, UsePipe,UseServiceLock
from app.depends.dependencies import get_auth_permission
from app.depends.variables import DeleteMode,delete_mode_query
from app.interface.delete_ingest import DeleteIngestDocumentInterface
from app.manager.broker_manager import Broker
from app.manager.merchant_manager import Merchant
from app.models.vector_model import DeleteCollectionModel, QdrantCollectionModel
from app.services.agent.remote_agent_service import RemoteAgentService
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from app.services.worker.arq_service import ArqIngestTaskService
from app.utils.constant import CostConstant
import aiohttp

@UseHandler(AsyncIOHandler,ServiceAvailabilityHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('vector')
class VectorDBRessource(BaseHTTPRessource,DeleteIngestDocumentInterface):
    
    @InjectInMethod()
    def __init__(self,arqService:ArqIngestTaskService,remoteAgentService:RemoteAgentService,configService:ConfigService):
        super().__init__(None,None)
        DeleteIngestDocumentInterface.__init__(self,arqService)
        self.arqService = arqService
        self.remoteAgentService = remoteAgentService
        self.configService = configService
        self.session: aiohttp.ClientSession | None = None
   
    async def on_startup(self):
        headers = {"Authorization": f"Bearer {self.remoteAgentService.auth_header}"}
        base_url = f"http://{self.remoteAgentService.agentic_http_host}/vector"

        async with aiohttp.ClientSession(base_url=base_url,headers=headers) as session:
            self.session = session

    async def on_shutdown(self):
        async with self.session as session:
            self.session.close()
    
    @UseLimiter('1/minutes')
    @PingService([RemoteAgentService])
    @UseHandler(AgenticHandler,ProxyRestGatewayHandler)
    @UseServiceLock(RemoteAgentService,lockType='reader')
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
    async def create_collection(self, request:Request,response:Response,collection:QdrantCollectionModel, autPermission:AuthPermission=Depends(get_auth_permission)):
        collection = collection.model_dump()

        async with self.session.post('/',json=collection) as res:
            res_body = await res.json()
            if res.status != status.HTTP_201_CREATED:
               raise aiohttp.ClientPayloadError(res_body,res.status)
            
            return {'collection':collection}

    @UseLimiter('30/minutes')
    @HTTPStatusCode(status.HTTP_200_OK)
    @PingService([RemoteAgentService])
    @UseHandler(AgenticHandler,ProxyRestGatewayHandler)
    @UseServiceLock(RemoteAgentService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/{collection_name}/',methods=[HTTPMethod.GET])
    async def get_collection(self, request:Request,response:Response,collection_name:str,autPermission:AuthPermission=Depends(get_auth_permission)):
        
        async with ( self.session.get(f'/') if not collection_name else self.session.get(f'/s/{collection_name}') )as res:
            res_body = await res.json()
            response.status_code = res.status
            return res_body
    
    @UseLimiter('1/minutes')
    @Throttle(uniform=(800,1500))
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UsePipe(DeleteDocumentIngestUpdate('vector'))
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @PingService([RedisService,RemoteAgentService,ArqIngestTaskService])
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @UseServiceLock(RedisService,RemoteAgentService,ArqIngestTaskService,lockType='reader')
    @UseHandler(AgenticHandler,CostHandler,ArqHandler,ProxyRestGatewayHandler,RedisHandler,DataIngestHandler)
    @BaseHTTPRessource.HTTPRoute('/{collection_name}/',methods=[HTTPMethod.DELETE],response_model=DeleteCollectionModel)
    async def delete_collection(self, request:Request,response:Response,collection_name:str,cost:Annotated[DeleteDocumentIngestCost,Depends(DeleteDocumentIngestCost)],merchant:Annotated[Merchant,Depends(Merchant)],broker:Annotated[Broker,Depends(Broker)],mode:DeleteMode = Depends(delete_mode_query), autPermission:AuthPermission=Depends(get_auth_permission)):
        """Delete all results and delete all enqueued job matching the collection_name filtered by the task_name """

        meta,jobs_done,jobs_queue,errors =  await self.delete_section('vector_config','collection_name',collection_name)
        

        async with self.session.delete(f'/{collection_name}',params={"mode":mode}) as res:
            res_body = await res.json()
            if res.status != status.HTTP_200_OK:
               raise aiohttp.ClientPayloadError(res_body,res.status)

        for j in jobs_queue:
            merchant.payment(
                self.arqService.abort,
                j,
                'vector_config'
                )
            
            merchant.wait(1)
    
        for j in jobs_done:
            merchant.payment(
                self.arqService.delete,
                j,
                'vector_config'
                )
        
        return DeleteCollectionModel(metadata=meta,gateway_body=res_body,job_dequeued=jobs_queue,jod_deleted=jobs_done,collection_name=collection_name,errors=errors)
            
    @UseLimiter('1/minutes')
    @Throttle(uniform=(800,1500))
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UsePipe(DeleteDocumentIngestUpdate('vector'))
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @PingService([RedisService,RemoteAgentService,ArqIngestTaskService])
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @UseServiceLock(RedisService,RemoteAgentService,ArqIngestTaskService,lockType='reader')
    @UseHandler(AgenticHandler,CostHandler,ArqHandler,ProxyRestGatewayHandler,RedisHandler,DataIngestHandler)
    @BaseHTTPRessource.HTTPRoute('/docs/{job_id}/',methods=[HTTPMethod.DELETE],response_model=DeleteCollectionModel)
    async def delete_documents(self,job_id:str, request:Request,response:Response,cost:Annotated[DeleteDocumentIngestCost,Depends(DeleteDocumentIngestCost)],broker:Annotated[Broker,Depends(Broker)],merchant:Annotated[Merchant,Depends(Merchant)],autPermission:AuthPermission=Depends(get_auth_permission)):
        """Delete result and the point associated with the job_id filtered by the task_name """

        meta,collection_name = await self.delete_single_document(job_id,'vector_config','vector','collection_name')

        async with self.session.delete(f'/docs/{collection_name}/{job_id}') as res:
            res_body = await res.json()
            if res.status != status.HTTP_200_OK:
               raise aiohttp.ClientPayloadError(res_body,res.status)
        
        merchant.payment(
            self.arqService.delete,
            job_id,
            'vector_config'
            )
        return DeleteCollectionModel(metadata=[meta],gateway_body=res_body,job_dequeued=[],jod_deleted=[job_id],collection_name=collection_name)
       
