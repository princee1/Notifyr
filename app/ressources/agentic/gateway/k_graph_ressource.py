from typing import Annotated
from fastapi import Depends, Request, Response
from app.classes.auth_permission import AuthPermission
from app.container import InjectInMethod
from app.cost.ingest_cost import DeleteDocumentIngestCost
from app.decorators.handlers import AgenticHandler, ArqHandler, AsyncIOHandler, CostHandler, DataIngestHandler, GraphitiHandler, GatewayHandler, RedisHandler, ServiceAvailabilityHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.permissions import JWTRouteHTTPPermission
from app.decorators.pipes import DeleteDocumentIngestUpdatePipe, MerchantPipe, domain_pipe, update_status_upon_no_metadata_pipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, Throttle, UseHandler, UseInterceptor, UseLimiter, UsePermission, UsePipe, LockService
from app.depends.dependencies import get_auth_permission
from app.interface.delete_ingest import DeleteIngestDocumentInterface
from app.manager.merchant_manager import Merchant
from app.models.graphiti_model import DeleteDomainModel, GraphitiSearchModel
from app.services.agent.remote_agent_service import RemoteAgentService
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from app.services.worker.arq_service import ArqIngestTaskService
from app.utils.constant import AgenticConstant, CostConstant
from fastapi import status

@UsePermission(JWTRouteHTTPPermission)
@UseHandler(AsyncIOHandler,ServiceAvailabilityHandler)
@HTTPRessource('k-graph')
class KGraphDBRessource(BaseHTTPRessource,DeleteIngestDocumentInterface):

    @InjectInMethod()
    def __init__(self,configService:ConfigService,arqService:ArqIngestTaskService,remoteAgentService:RemoteAgentService):
        super().__init__(None,None)
        DeleteIngestDocumentInterface.__init__(self,arqService)
        self.configService = configService
        self.arqService = arqService
        self.remoteAgentService = remoteAgentService

    @Throttle(normal=(300,40))
    @UseHandler(GraphitiHandler,GatewayHandler)
    @UseHandler(AgenticHandler)
    @PingService([RemoteAgentService])
    @LockService(RemoteAgentService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/document/{document_id}/',methods=[HTTPMethod.GET])
    async def get_document_graph(self,document_id:str,response:Response,request:Request,authPermission:AuthPermission = Depends(get_auth_permission)):
        gateway_body = await self.remoteAgentService.request('POST', AgenticConstant.K_GRAPH_ROUTER(f'/document/{document_id}/'))
        return gateway_body

    @UsePipe(domain_pipe)
    @UseHandler(GraphitiHandler,GatewayHandler)
    @UseHandler(AgenticHandler)
    @PingService([RemoteAgentService])
    @LockService(RemoteAgentService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/domain/{domain}/',methods=[HTTPMethod.GET])
    async def get_domain_graph(self,domain:str,response:Response,request:Request,authPermission:AuthPermission = Depends(get_auth_permission)):
        gateway_body = await self.remoteAgentService.request('POST', AgenticConstant.K_GRAPH_ROUTER(f'/document/{domain}/'))
        return gateway_body

    @UsePipe(MerchantPipe(-1))
    @Throttle(uniform=(1000,1800))
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UsePipe(DeleteDocumentIngestUpdatePipe('graph'))
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @PingService([RedisService,RemoteAgentService,ArqIngestTaskService])
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @LockService(RedisService,RemoteAgentService,ArqIngestTaskService,lockType='reader')
    @UseHandler(GraphitiHandler,AgenticHandler,CostHandler,ArqHandler,GatewayHandler,RedisHandler,DataIngestHandler)
    @BaseHTTPRessource.HTTPRoute('/document/{job_id}/',methods=[HTTPMethod.DELETE],response_model=DeleteDomainModel)
    async def delete_document(self,job_id:str,response:Response,request:Request,cost:Annotated[DeleteDocumentIngestCost,Depends(DeleteDocumentIngestCost)],merchant:Annotated[Merchant,Depends(Merchant)],authPermission:AuthPermission = Depends(get_auth_permission)):
        
        meta,domain = await self.delete_single_document(job_id,'graph_config','graph','domain')
        gateway_body = await self.remoteAgentService.request('DELETE', AgenticConstant.K_GRAPH_ROUTER(f'/document/{job_id}'))
                
        merchant.payment(
            self.arqService.delete,
            job_id,
            'graph_config'
            )
        
        return DeleteDomainModel(metadata=[meta],errors={},domain=domain,gateway_body=gateway_body,job_dequeued=[],job_deleted=[job_id])

    @Throttle(uniform=(1500,2500))
    @UsePipe(domain_pipe,MerchantPipe(-1))
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UsePipe(DeleteDocumentIngestUpdatePipe('graph'))
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @PingService([RedisService,RemoteAgentService,ArqIngestTaskService])
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @LockService(RedisService,RemoteAgentService,ArqIngestTaskService,lockType='reader')
    @UseHandler(GraphitiHandler,AgenticHandler,CostHandler,ArqHandler,GatewayHandler,RedisHandler,DataIngestHandler)
    @BaseHTTPRessource.HTTPRoute('/domain/{domain}/',methods=[HTTPMethod.DELETE],response_model=DeleteDomainModel)
    async def delete_domain(self,domain:str,response:Response,request:Request,cost:Annotated[DeleteDocumentIngestCost,Depends(DeleteDocumentIngestCost)],merchant:Annotated[Merchant,Depends(Merchant)],authPermission:AuthPermission = Depends(get_auth_permission)):
        
        meta,jobs_done,jobs_queue,errors =  await self.delete_section('graph_config','domain',domain)
        gateway_body = await self.remoteAgentService.request('DELETE', AgenticConstant.K_GRAPH_ROUTER(f'/domain/{domain}'))

        for j in jobs_queue:
            merchant.payment(
                self.arqService.abort,
                j,
                'graph_config'
                )
            
            merchant.wait(1)
    
        for j in jobs_done:
            merchant.payment(
                self.arqService.delete,
                j,
                'graph_config'
                )
        
        return DeleteDomainModel(metadata=meta,gateway_body=gateway_body,job_dequeued=jobs_queue,jod_deleted=jobs_done,domain=domain,errors=errors)

    @UseLimiter('20/hour')
    @Throttle(uniform=(200,500))
    @HTTPStatusCode(status.HTTP_200_OK)
    @PingService([RemoteAgentService])
    @UseHandler(AgenticHandler,GraphitiHandler,GatewayHandler)
    @LockService(RemoteAgentService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/playground/',methods=[HTTPMethod.POST])
    async def playground(self,response:Response,request:Request,search:GraphitiSearchModel,authPermission:AuthPermission= Depends(get_auth_permission)):
        ...
