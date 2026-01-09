from typing import Annotated
from fastapi import Depends, Request, Response, status
from app.classes.auth_permission import AuthPermission
from app.container import InjectInMethod
from app.cost.file_cost import FileCost
from app.decorators.guards import ArqDataTaskGuard
from app.decorators.handlers import ArqHandler, AsyncIOHandler, CostHandler, ProxyRestGatewayHandler, ServiceAvailabilityHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.permissions import JWTRouteHTTPPermission
from app.decorators.pipes import update_status_upon_no_metadata_pipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, UseGuard, UseHandler, UseInterceptor, UseLimiter, UsePermission, UsePipe,UseServiceLock
from app.depends.dependencies import get_auth_permission
from app.depends.variables import DeleteMode,delete_mode_query
from app.manager.broker_manager import Broker
from app.models.data_ingest_model import IngestDataUriMetadata
from app.models.file_model import UriMetadata
from app.models.vector_model import DeleteCollectionModel, QdrantCollectionModel
from app.services.agent.remote_agent_service import RemoteAgentService
from app.services.config_service import ConfigService
from app.services.worker.arq_service import ArqDataTaskService, JobStatus, JobStatusNotValidError
from app.utils.constant import ArqDataTaskConstant, CostConstant
import aiohttp

@UseHandler(AsyncIOHandler,ServiceAvailabilityHandler)
@UseServiceLock(RemoteAgentService,lockType='reader')
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('vector')
class VectorDBRessource(BaseHTTPRessource):
    
    @InjectInMethod()
    def __init__(self,arqService:ArqDataTaskService,remoteAgentService:RemoteAgentService,configService:ConfigService):
        super().__init__(None,None)
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
    @UseHandler(ProxyRestGatewayHandler)
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
    @UseHandler(ProxyRestGatewayHandler)
    @BaseHTTPRessource.HTTPRoute('/{collection_name}/',methods=[HTTPMethod.GET])
    async def get_collection(self, request:Request,response:Response,collection_name:str,autPermission:AuthPermission=Depends(get_auth_permission)):
        
        async with ( self.session.get(f'/all') if not collection_name else self.session.get(f'/{collection_name}') )as res:
            res_body = await res.json()
            response.status_code = res.status
            return res_body
    
    @UseLimiter('1/minutes')
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @PingService([RemoteAgentService,ArqDataTaskService])
    @UseServiceLock(ArqDataTaskService,lockType='reader')
    @UseHandler(CostHandler,ArqHandler,ProxyRestGatewayHandler)
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @BaseHTTPRessource.HTTPRoute('/{collection_name}/',methods=[HTTPMethod.DELETE],response_model=DeleteCollectionModel)
    async def delete_collection(self, request:Request,response:Response,collection_name:str,cost:Annotated[FileCost,Depends(FileCost)],broker:Annotated[Broker,Depends(Broker)],mode:DeleteMode = Depends(delete_mode_query), autPermission:AuthPermission=Depends(get_auth_permission)):
        """Delete all results and delete all enqueued job matching the collection_name filtered by the task_name """

        jobs_queue = []
        jobs_done = []
        meta = []

        for job in [*await self.arqService.get_queued_jobs(),*await self.arqService.get_jobs_results()]:
            if job.kwargs.get('collection_name',None) == collection_name:
                size,sha,uri = job.kwargs.get('size',0),job.kwargs('sha','unknown'),job.kwargs.get('uri',None)
                if not hasattr(job,'result'):
                    jobs_queue.append(job.job_id)
                jobs_done.append(job.job_id)

                meta.append(IngestDataUriMetadata(uri,size,sha))

        async with self.session.delete(f'/{collection_name}',params={"mode":mode}) as res:
            res_body = await res.json()
            if res.status != status.HTTP_200_OK:
               raise aiohttp.ClientPayloadError(res_body,res.status)
    
        for j in jobs_queue:
            broker.add(self.arqService.abort,j)
            broker.wait(1)
    
        for j in jobs_done:
            broker.add(self.arqService.delete,j)

        return DeleteCollectionModel(metadata=meta,gateway_body=res_body,job_dequeued=jobs_queue,jod_deleted=jobs_done)
            
    @UseLimiter('1/minutes')
    @PingService([RemoteAgentService,ArqDataTaskService])
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @UseServiceLock(ArqDataTaskService,lockType='reader')
    @UseHandler(CostHandler,ArqHandler,ProxyRestGatewayHandler)
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @BaseHTTPRessource.HTTPRoute('/docs/{job_id}/',methods=[HTTPMethod.DELETE])
    async def delete_documents(self,job_id:str, request:Request,response:Response,cost:Annotated[FileCost,Depends(FileCost)],broker:Annotated[Broker,Depends(Broker)],autPermission:AuthPermission=Depends(get_auth_permission)):
        """Delete result and the point associated with the job_id filtered by the task_name """

        job,state = await self.arqService.exists(job_id,return_status=True)

        if state != JobStatus.complete:
            raise JobStatusNotValidError(job_id,state)
        
        info = await self.arqService.info(job)
        collection_name = info.kwargs['collection_name']
        meta = UriMetadata(uri = info.kwargs['uri'],size = info.kwargs.get('size',0))

        async with self.session.delete(f'/docs/{collection_name}/{job_id}') as res:
            res_body = await res.json()
            if res.status != status.HTTP_200_OK:
               raise aiohttp.ClientPayloadError(res_body,res.status)
        
        broker.add(self.arqService.delete,job_id)
        return DeleteCollectionModel(metadata=[meta],gateway_body=res_body,job_dequeued=[],jod_deleted=[job_id])
       
