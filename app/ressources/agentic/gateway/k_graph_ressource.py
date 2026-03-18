from typing import Annotated
import aiohttp
from fastapi import Depends, Request, Response
from app.classes.auth_permission import AuthPermission
from app.container import InjectInMethod
from app.decorators.handlers import AgenticHandler, ArqHandler, AsyncIOHandler, CostHandler, DataIngestHandler, GraphitiHandler, ProxyRestGatewayHandler, RedisHandler, ServiceAvailabilityHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.permissions import JWTRouteHTTPPermission
from app.decorators.pipes import MerchantPipe, domain_pipe, update_status_upon_no_metadata_pipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, Throttle, UseHandler, UseInterceptor, UseLimiter, UsePermission, UsePipe, UseServiceLock
from app.depends.dependencies import get_auth_permission
from app.errors.ingest_error import IngestConfigNotPresentError
from app.manager.merchant_manager import Merchant
from app.models.graphiti_model import DeleteDomainModel, GraphitiSearchModel
from app.models.ingest_model import IngestDataUriMetadata
from app.services.agent.remote_agent_service import RemoteAgentService
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from app.services.worker.arq_service import ArqIngestTaskService, JobStatusNotValidError,JobStatus
from app.utils.constant import CostConstant, GraphitiConstant
from fastapi import status

@UsePermission(JWTRouteHTTPPermission)
@UseHandler(AsyncIOHandler,ServiceAvailabilityHandler)
@HTTPRessource('k-graph')
class KGraphDBRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,configService:ConfigService,arqService:ArqIngestTaskService,remoteAgentService:RemoteAgentService):
        super().__init__(None,None)
        self.configService = configService
        self.arqService = arqService
        self.remoteAgentService = remoteAgentService

    async def on_startup(self):
        headers = {"Authorization": f"Bearer {self.remoteAgentService.auth_header}"}
        base_url = f"http://{self.remoteAgentService.agentic_http_host}/k-graph/"

        async with aiohttp.ClientSession(base_url=base_url,headers=headers) as session:
            self.session = session

    async def on_shutdown(self):
        async with self.session as session:
            self.session.close()

    @Throttle(normal=(300,40))
    @UseHandler(GraphitiHandler,ProxyRestGatewayHandler)
    @UseHandler(AgenticHandler)
    @PingService([RemoteAgentService])
    @UseServiceLock(RemoteAgentService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/document/{document_id}/',methods=[HTTPMethod.GET])
    async def get_document_graph(self,document_id:str,response:Response,request:Request,authPermission:AuthPermission = Depends(get_auth_permission)):

        async with self.session.post(f'/document/{document_id}/') as res:
            res_body = await res.json()
            if res.status != status.HTTP_200_OK:
               raise aiohttp.ClientPayloadError(res_body,res.status)
            
            return res_body

    @UsePipe(domain_pipe)
    @UseHandler(GraphitiHandler,ProxyRestGatewayHandler)
    @UseHandler(AgenticHandler)
    @PingService([RemoteAgentService])
    @UseServiceLock(RemoteAgentService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/domain/{domain}/',methods=[HTTPMethod.GET])
    async def get_domain_graph(self,domain:str,response:Response,request:Request,authPermission:AuthPermission = Depends(get_auth_permission)):
        
        async with self.session.post(f'/document/{domain}/') as res:
            res_body = await res.json()
            if res.status != status.HTTP_200_OK:
               raise aiohttp.ClientPayloadError(res_body,res.status)
            
            return res_body

    @UsePipe(MerchantPipe(-1))
    @Throttle(uniform=(1000,1800))
    @PingService([RedisService,RemoteAgentService,ArqIngestTaskService])
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @UseServiceLock(RedisService,RemoteAgentService,ArqIngestTaskService,lockType='reader')
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @UseHandler(GraphitiHandler,AgenticHandler,CostHandler,ArqHandler,ProxyRestGatewayHandler,RedisHandler,DataIngestHandler)
    @BaseHTTPRessource.HTTPRoute('/document/{job_id}/',methods=[HTTPMethod.DELETE],response_model=DeleteDomainModel)
    async def delete_document(self,job_id:str,response:Response,request:Request,merchant:Annotated[Merchant,Depends(Merchant)],authPermission:AuthPermission = Depends(get_auth_permission)):
        
        job,state = await self.arqService.exists(job_id,return_status=True)

        if state != JobStatus.complete:
            raise JobStatusNotValidError(job_id,state)
        
        info = await self.arqService.info(job)
        graph_config:dict = info.kwargs.get('graph_config',None)

        if not graph_config:
            raise IngestConfigNotPresentError('graph_config','graph')
        
        size = info.kwargs.get('size',0) /2 if info.kwargs.get('vector_config',None) != None else info.kwargs.get('size',0)
        
        meta = IngestDataUriMetadata(uri = info.kwargs['uri'],size = size,sha=info.kwargs.get('sha','unknown'))

        domain = info.kwargs.get('domain',None)

        async with self.session.delete(f'/document/{job_id}') as res:
            res_body = await res.json()
            if res.status != status.HTTP_200_OK:
               raise aiohttp.ClientPayloadError(res_body,res.status)
                
        merchant.payment(
            self.arqService.delete,
            job_id,
            'graph_config'
            )
        
        return DeleteDomainModel(metadata=[meta],errors={},domain=domain,gateway_body=res_body,job_dequeued=[],job_deleted=[job_id])

    @Throttle(uniform=(1500,2500))
    @UsePipe(domain_pipe,MerchantPipe(-1))
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @PingService([RedisService,RemoteAgentService,ArqIngestTaskService])
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @UseServiceLock(RedisService,RemoteAgentService,ArqIngestTaskService,lockType='reader')
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @UseHandler(GraphitiHandler,AgenticHandler,CostHandler,ArqHandler,ProxyRestGatewayHandler,RedisHandler,DataIngestHandler)
    @BaseHTTPRessource.HTTPRoute('/domain/{domain}/',methods=[HTTPMethod.DELETE],response_model=DeleteDomainModel)
    async def delete_domain(self,domain:str,response:Response,request:Request,merchant:Annotated[Merchant,Depends(Merchant)],authPermission:AuthPermission = Depends(get_auth_permission)):
        
        jobs_queue = []
        jobs_done = []
        meta = []

        for job in [*await self.arqService.get_queued_jobs(),*await self.arqService.get_jobs_results()]:
            if job.kwargs.get('graph_config',None) != None and job.kwargs.get('graph_config',{}).get('domain',None) == domain:
                size,sha,uri = job.kwargs.get('size',0),job.kwargs('sha','unknown'),job.kwargs.get('uri',None)
                if not hasattr(job,'result'):
                    jobs_queue.append(job.job_id)
                jobs_done.append(job.job_id)

                meta.append(IngestDataUriMetadata(uri,size,sha))

        async with self.session.delete(f'/domain/{domain}') as res:
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
        
        return DeleteDomainModel(metadata=meta,gateway_body=res_body,job_dequeued=jobs_queue,jod_deleted=jobs_done,domain=domain)

    @UseLimiter('20/hour')
    @Throttle(uniform=(200,500))
    @HTTPStatusCode(status.HTTP_200_OK)
    @PingService([RemoteAgentService])
    @UseHandler(AgenticHandler,GraphitiHandler,ProxyRestGatewayHandler)
    @UseServiceLock(RemoteAgentService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/playground/',methods=[HTTPMethod.POST])
    async def playground(self,response:Response,request:Request,search:GraphitiSearchModel,authPermission:AuthPermission= Depends(get_auth_permission)):
        ...
