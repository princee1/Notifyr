from typing import Annotated
from fastapi import Depends, Request, Response
from app.classes.auth_permission import AccessAPIInfo, AuthPermission, ClientAccessInfo, ClientType, Role
from app.container import InjectInMethod
from app.cost.ingest_cost import DeleteDocumentIngestCost
from app.decorators.handlers import AgenticHandler, ArqHandler, AsyncIOHandler, CostHandler, DataIngestHandler, GraphitiHandler, GatewayHandler, RedisHandler, ServiceAvailabilityHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.permissions import AdminPermission, ClientTypesPermission, JWTRouteHTTPPermission, UserPermission
from app.decorators.pipes import DeleteDocumentIngestUpdatePipe, MerchantPipe,  domain_pipe, update_status_upon_no_metadata_pipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, Throttle, UseAccess, UseHandler, UseInterceptor, UseLimiter, UsePermission, UsePipe, LockService, UseRoles
from app.depends.dependencies import get_access_info, get_auth_permission, get_client_info
from app.depends.funcs_dep import get_issuer
from app.interface.delete_ingest import DeleteIngestDocumentInterface
from app.manager.issuer_manager import IssuerManager
from app.manager.merchant_manager import Merchant
from app.models.graphiti_model import DeleteDomainModel, GraphitiSearchModel
from app.services.agent.remote_agent_service import RemoteAgentService
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from app.services.worker.arq_service import ArqIngestTaskService
from app.utils.constant import AgenticConstant, CostConstant
from fastapi import status

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
    @UseHandler(AgenticHandler)
    @PingService([RemoteAgentService])
    @UseHandler(GraphitiHandler,GatewayHandler)
    @UseRoles([Role.AGENT,Role.INGEST,Role.ADMIN])
    @LockService(RemoteAgentService,lockType='reader')
    @UseAccess(accesses={'Admin':True,'System':True,'User':True})
    @UsePermission(JWTRouteHTTPPermission,ClientTypesPermission(['Admin','System','User']))
    @BaseHTTPRessource.HTTPRoute('/document/{document_id}/',methods=[HTTPMethod.GET])
    async def get_document_graph(self,document_id:str,response:Response,request:Request,authPermission:AuthPermission = Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info), accessInfo:AccessAPIInfo = Depends(get_access_info) ):
        gateway_body = await self.remoteAgentService.request('GET', AgenticConstant.K_GRAPH_ROUTER(f'/document/{document_id}/'))
        return gateway_body

    @UsePipe(domain_pipe)
    @UseHandler(AgenticHandler)
    @PingService([RemoteAgentService])
    @UseHandler(GraphitiHandler,GatewayHandler)
    @UseRoles([Role.AGENT,Role.INGEST,Role.ADMIN])
    @LockService(RemoteAgentService,lockType='reader')
    @UseAccess(accesses={'Admin':True,'System':True,'User':True})
    @UsePermission(JWTRouteHTTPPermission,ClientTypesPermission(['Admin','System','User']))
    @BaseHTTPRessource.HTTPRoute('/domain/{domain}/',methods=[HTTPMethod.GET])
    async def get_domain_graph(self,domain:str,response:Response,request:Request,authPermission:AuthPermission = Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info), accessInfo:AccessAPIInfo = Depends(get_access_info) ):
        gateway_body = await self.remoteAgentService.request('GET', AgenticConstant.K_GRAPH_ROUTER(f'/document/{domain}/'))
        return gateway_body


    @Throttle(uniform=(1000,1800))
    @UseRoles([Role.INGEST,Role.ADMIN])
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @UseAccess(accesses={'Admin':True,'System':True,'User':True})
    @UsePipe(MerchantPipe(-1),DeleteDocumentIngestUpdatePipe('graph'))
    @PingService([RedisService,RemoteAgentService,ArqIngestTaskService])
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @LockService(RedisService,RemoteAgentService,ArqIngestTaskService,lockType='reader')
    @UsePermission(JWTRouteHTTPPermission,ClientTypesPermission(['Admin','User','System']))
    @UseHandler(GraphitiHandler,AgenticHandler,CostHandler,ArqHandler,GatewayHandler,RedisHandler,DataIngestHandler)
    @BaseHTTPRessource.HTTPRoute('/document/{job_id}/',methods=[HTTPMethod.DELETE],response_model=DeleteDomainModel)
    async def delete_document(self,job_id:str,response:Response,request:Request,cost:Annotated[DeleteDocumentIngestCost,Depends(DeleteDocumentIngestCost)],merchant:Annotated[Merchant,Depends(Merchant)],issuer:Annotated[IssuerManager,Depends(IssuerManager)], authPermission:AuthPermission = Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info), accessInfo:AccessAPIInfo = Depends(get_access_info) ):
        
        meta,domain = await self.delete_single_document(job_id,'graph_config','graph','domain',issuer.verify_ownership)
        gateway_body = await self.remoteAgentService.request('DELETE', AgenticConstant.K_GRAPH_ROUTER(f'/document/{job_id}'))
                
        merchant.payment(
            self.arqService.delete,
            job_id,
            'graph_config'
            )
        
        return DeleteDomainModel(metadata=[meta],errors={},domain=domain,gateway_body=gateway_body,job_dequeued=[],job_deleted=[job_id])

    
    @Throttle(uniform=(1500,2500))
    @UseRoles([Role.INGEST,Role.ADMIN])
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @UseAccess(accesses={'Admin':True,'System':True,'User':True})
    @PingService([RedisService,RemoteAgentService,ArqIngestTaskService])
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @UsePipe(domain_pipe,MerchantPipe(-1),DeleteDocumentIngestUpdatePipe('graph'))
    @LockService(RedisService,RemoteAgentService,ArqIngestTaskService,lockType='reader')
    @UsePermission(JWTRouteHTTPPermission,ClientTypesPermission(['Admin','System','User']))
    @UseHandler(GraphitiHandler,AgenticHandler,CostHandler,ArqHandler,GatewayHandler,RedisHandler,DataIngestHandler)
    @BaseHTTPRessource.HTTPRoute('/domain/{domain}/',methods=[HTTPMethod.DELETE],response_model=DeleteDomainModel)
    async def delete_domain(self,domain:str,response:Response,request:Request,cost:Annotated[DeleteDocumentIngestCost,Depends(DeleteDocumentIngestCost)],merchant:Annotated[Merchant,Depends(Merchant)],issuer:Annotated[IssuerManager,Depends(IssuerManager)],authPermission:AuthPermission = Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info), accessInfo:AccessAPIInfo = Depends(get_access_info) ):
        
        meta,jobs_done,jobs_queue,errors =  await self.delete_section('graph_config','domain',domain,issuer.verify_ownership)
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

    
    @Throttle(uniform=(200,500))
    @PingService([RemoteAgentService])
    @HTTPStatusCode(status.HTTP_200_OK)
    @UseRoles([Role.AGENT,Role.ADMIN,Role.INGEST])
    @UseLimiter('24/hour',cost={'App':3,'User':2})
    @LockService(RemoteAgentService,lockType='reader')
    @UseHandler(AgenticHandler,GraphitiHandler,GatewayHandler)
    @UseAccess(accesses={'Admin':True,'System':True,'User':True,'App':True})
    @UsePermission(JWTRouteHTTPPermission,ClientTypesPermission([ClientType.Service,ClientType.Twilio],'exclude'))
    @BaseHTTPRessource.HTTPRoute('/playground/',methods=[HTTPMethod.POST])
    async def playground(self,response:Response,request:Request,search:GraphitiSearchModel,issuer:Annotated[IssuerManager,Depends(IssuerManager)],authPermission:AuthPermission= Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info), accessInfo:AccessAPIInfo = Depends(get_access_info) ):
        ...
