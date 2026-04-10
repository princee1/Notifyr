from typing import Annotated
from fastapi import Depends, Request, Response, status
from app.classes.auth_permission import AuthPermission
from app.container import InjectInMethod
from app.cost.ingest_cost import DeleteDocumentIngestCost
from app.decorators.handlers import AgenticHandler, ArqHandler, AsyncIOHandler, CostHandler, DataIngestHandler, GatewayHandler, RedisHandler, ServiceAvailabilityHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.permissions import JWTRouteHTTPPermission
from app.decorators.pipes import DeleteDocumentIngestUpdatePipe, update_status_upon_no_metadata_pipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, Throttle, UseGuard, UseHandler, UseInterceptor, UseLimiter, UsePermission, UsePipe,LockService
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
from app.utils.constant import AgenticConstant, CostConstant
 
BASE_AGENTIC_PATH = '/vector'

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
    
    @UseLimiter('1/minutes')
    @PingService([RemoteAgentService])
    @UseHandler(AgenticHandler,GatewayHandler)
    @LockService(RemoteAgentService,lockType='reader')
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
    async def create_collection(self, request:Request,response:Response,collection:QdrantCollectionModel, autPermission:AuthPermission=Depends(get_auth_permission)):
        collection = collection.model_dump()
        await self.remoteAgentService.request('POST', AgenticConstant.VECTOR_ROUTER('/'),
                                            json=collection,
                                            expected_status=status.HTTP_201_CREATED)
        return {'collection': collection}

    @UseLimiter('30/minutes')
    @HTTPStatusCode(status.HTTP_200_OK)
    @PingService([RemoteAgentService])
    @UseHandler(AgenticHandler,GatewayHandler)
    @LockService(RemoteAgentService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/{collection_name}/',methods=[HTTPMethod.GET])
    async def get_collection(self, request:Request,response:Response,collection_name:str,autPermission:AuthPermission=Depends(get_auth_permission)):
        
        path = f'/' if not collection_name else f'/s/{collection_name}'
        path = AgenticConstant.VECTOR_ROUTER(path)
        gateway_body = await self.remoteAgentService.request('GET', path, expected_status=status.HTTP_200_OK)
        return gateway_body
    
    @UseLimiter('1/minutes')
    @Throttle(uniform=(800,1500))
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UsePipe(DeleteDocumentIngestUpdatePipe('vector'))
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @PingService([RedisService,RemoteAgentService,ArqIngestTaskService])
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @LockService(RedisService,RemoteAgentService,ArqIngestTaskService,lockType='reader')
    @UseHandler(AgenticHandler,CostHandler,ArqHandler,GatewayHandler,RedisHandler,DataIngestHandler)
    @BaseHTTPRessource.HTTPRoute('/{collection_name}/',methods=[HTTPMethod.DELETE],response_model=DeleteCollectionModel)
    async def delete_collection(self, request:Request,response:Response,collection_name:str,cost:Annotated[DeleteDocumentIngestCost,Depends(DeleteDocumentIngestCost)],merchant:Annotated[Merchant,Depends(Merchant)],broker:Annotated[Broker,Depends(Broker)],mode:DeleteMode = Depends(delete_mode_query), autPermission:AuthPermission=Depends(get_auth_permission)):
        """Delete all results and delete all enqueued job matching the collection_name filtered by the task_name """

        meta,jobs_done,jobs_queue,errors =  await self.delete_section('vector_config','collection_name',collection_name)
        gateway_body = await self.remoteAgentService.request('DELETE',
                                                        AgenticConstant.VECTOR_ROUTER(f'/{collection_name}'),
                                                        params={"mode": mode},
                                                        expected_status=status.HTTP_200_OK)
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
        
        return DeleteCollectionModel(metadata=meta,gateway_body=gateway_body,job_dequeued=jobs_queue,jod_deleted=jobs_done,collection_name=collection_name,errors=errors)
            
    @UseLimiter('1/minutes')
    @Throttle(uniform=(800,1500))
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UsePipe(DeleteDocumentIngestUpdatePipe('vector'))
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @PingService([RedisService,RemoteAgentService,ArqIngestTaskService])
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @LockService(RedisService,RemoteAgentService,ArqIngestTaskService,lockType='reader')
    @UseHandler(AgenticHandler,CostHandler,ArqHandler,GatewayHandler,RedisHandler,DataIngestHandler)
    @BaseHTTPRessource.HTTPRoute('/docs/{job_id}/',methods=[HTTPMethod.DELETE],response_model=DeleteCollectionModel)
    async def delete_documents(self,job_id:str, request:Request,response:Response,cost:Annotated[DeleteDocumentIngestCost,Depends(DeleteDocumentIngestCost)],broker:Annotated[Broker,Depends(Broker)],merchant:Annotated[Merchant,Depends(Merchant)],autPermission:AuthPermission=Depends(get_auth_permission)):
        """Delete result and the point associated with the job_id filtered by the task_name """

        meta,collection_name = await self.delete_single_document(job_id,'vector_config','vector','collection_name')

        gateway_body = await self.remoteAgentService.request('DELETE',
                                                        AgenticConstant.VECTOR_ROUTER(f'/docs/{collection_name}/{job_id}'),
                                                        expected_status=status.HTTP_200_OK)
        
        merchant.payment(
            self.arqService.delete,
            job_id,
            'vector_config'
            )
        return DeleteCollectionModel(metadata=[meta],gateway_body=gateway_body,job_dequeued=[],jod_deleted=[job_id],collection_name=collection_name)
       
