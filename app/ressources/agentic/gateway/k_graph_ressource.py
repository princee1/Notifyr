from typing import Annotated
import aiohttp
from fastapi import Depends, Request, Response
from app.classes.auth_permission import AuthPermission
from app.container import InjectInMethod
from app.decorators.handlers import ArqHandler, AsyncIOHandler, CostHandler, DataIngestHandler, GraphitiHandler, ProxyRestGatewayHandler, RedisHandler, ServiceAvailabilityHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.permissions import JWTRouteHTTPPermission
from app.decorators.pipes import MerchantPipe, domain_pipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, Throttle, UseHandler, UseInterceptor, UseLimiter, UsePermission, UsePipe, UseServiceLock
from app.depends.dependencies import get_auth_permission
from app.manager.merchant_manager import Merchant
from app.services.agent.remote_agent_service import RemoteAgentService
from app.services.config_service import ConfigService
from app.services.worker.arq_service import ArqDataTaskService
from app.utils.constant import CostConstant, GraphitiConstant
from fastapi import status

@UsePermission(JWTRouteHTTPPermission)
@UseHandler(AsyncIOHandler,ServiceAvailabilityHandler)
@HTTPRessource('k-graph')
class KGraphDBRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,configService:ConfigService,arqService:ArqDataTaskService,remoteAgentService:RemoteAgentService):
        super().__init__(None,None)
        self.configService = configService
        self.arqService = arqService
        self.remoteAgentService = remoteAgentService

    async def on_startup(self):
        headers = {"Authorization": f"Bearer {self.remoteAgentService.auth_header}"}
        base_url = f"http://{self.remoteAgentService.agentic_http_host}/k-graph"

        async with aiohttp.ClientSession(base_url=base_url,headers=headers) as session:
            self.session = session

    async def on_shutdown(self):
        async with self.session as session:
            self.session.close()

    @UseHandler(GraphitiHandler,ProxyRestGatewayHandler)
    @BaseHTTPRessource.HTTPRoute('/document/{document_id}/',methods=[HTTPMethod.GET])
    async def get_document_graph(self,document_id:str,response:Response,request:Request,authPermission:AuthPermission = Depends(get_auth_permission)):
        ...

    @UsePipe(domain_pipe)
    @UseHandler(GraphitiHandler,ProxyRestGatewayHandler)
    @BaseHTTPRessource.HTTPRoute('/domain/{domain}/',methods=[HTTPMethod.GET])
    async def get_domain_graph(self,domain:str,response:Response,request:Request,authPermission:AuthPermission = Depends(get_auth_permission)):
        ...

    @UsePipe(MerchantPipe(-1))
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UseServiceLock(ArqDataTaskService,lockType='reader')
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @UseHandler(GraphitiHandler,CostHandler,ArqHandler,ProxyRestGatewayHandler,RedisHandler,DataIngestHandler)
    @BaseHTTPRessource.HTTPRoute('/document/{document_id}/',methods=[HTTPMethod.DELETE])
    async def delete_document(self,document_id:str,response:Response,request:Request,merchant:Annotated[Merchant,Depends(Merchant)],authPermission:AuthPermission = Depends(get_auth_permission)):
        ...

    @UsePipe(domain_pipe,MerchantPipe(-1))
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UseServiceLock(ArqDataTaskService,lockType='reader')
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @UseHandler(GraphitiHandler,CostHandler,ArqHandler,ProxyRestGatewayHandler,RedisHandler,DataIngestHandler)
    @BaseHTTPRessource.HTTPRoute('/domain/{domain}/',methods=[HTTPMethod.DELETE])
    async def delete_domain(self,domain:str,response:Response,request:Request,merchant:Annotated[Merchant,Depends(Merchant)],authPermission:AuthPermission = Depends(get_auth_permission)):
        ...

    @UseLimiter('20/hour')
    @Throttle(uniform=(200,500))
    @HTTPStatusCode(status.HTTP_200_OK)
    @UseHandler(GraphitiHandler,ProxyRestGatewayHandler)
    @BaseHTTPRessource.HTTPRoute('/playground/',methods=[HTTPMethod.POST])
    async def playground(self,response:Response,request:Request,authPermission:AuthPermission= Depends(get_auth_permission)):
        ...


    # @BaseHTTPRessource.HTTPRoute('/document/{}/')
    # async def get_node(self,uuid:str):
    #     ...
    
    # @BaseHTTPRessource.HTTPRoute('/document/{}/')
    # async def delete_node(self,uuid:str):
    #     ...