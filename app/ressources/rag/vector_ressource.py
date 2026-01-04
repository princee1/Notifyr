from typing import Annotated

from fastapi import Depends, Request, Response
from app.classes.auth_permission import AuthPermission
from app.container import InjectInMethod
from app.cost.file_cost import FileCost
from app.decorators.guards import ArqDataTaskGuard
from app.decorators.handlers import ArqHandler, CostHandler, ProxyRestGatewayHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.pipes import ArqJobIdPipe
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UseGuard, UseHandler, UseInterceptor, UseLimiter, UsePermission, UsePipe
from app.depends.dependencies import get_auth_permission
from app.services.agent.remote_agent_service import RemoteAgentService
from app.services.config_service import ConfigService
from app.services.worker.arq_service import ArqDataTaskService
from app.utils.constant import ArqDataTaskConstant, CostConstant
import aiohttp

@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('vector')
class VectorDBRessource(BaseHTTPRessource):
    ...

    @InjectInMethod()
    def __init__(self,arqService:ArqDataTaskService,remoteAgentService:RemoteAgentService,configService:ConfigService):
        super().__init__(None,None)
        self.arqService = arqService
        self.remoteAgentService = remoteAgentService
        self.configService = configService
        self.session: aiohttp.ClientSession | None = None
   
    async def on_startup(self):
        headers = {"Authorization": f"Bearer {self.remoteAgentService.auth_header}"}
        base_url = f"http://{self.remoteAgentService.agentic_http_host}/vector/"

        async with aiohttp.ClientSession(base_url=base_url,headers=headers) as session:
            self.session = session

    async def on_shutdown(self):
        async with self.session as session:
            self.session.close()
    
    @UseLimiter('1/minutes')
    @UseHandler(ProxyRestGatewayHandler)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
    async def create_collection(self, request:Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        async with self.session.post() as response:
            ...

    @UseLimiter('30/minutes')
    @UseHandler(ProxyRestGatewayHandler)
    @BaseHTTPRessource.HTTPRoute('/{collection_name}',methods=[HTTPMethod.GET])
    async def get_collection(self, request:Request,response:Response,collection_name:str,autPermission:AuthPermission=Depends(get_auth_permission)):
        async with self.session.get() as response:
            ...


    @UseLimiter('1/minutes')
    @UseHandler(ProxyRestGatewayHandler)
    @BaseHTTPRessource.HTTPRoute('/{collection_name}',methods=[HTTPMethod.PUT],mount=False)
    async def update_collection(self, request:Request,response:Response,collection_name:str,):
        ...

    @UseLimiter('1/minutes')
    @UseHandler(CostHandler,ArqHandler,ProxyRestGatewayHandler)
    @UseGuard(ArqDataTaskGuard(ArqDataTaskConstant.FILE_DATA_TASK))
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @BaseHTTPRessource.HTTPRoute('/{collection_name}',methods=[HTTPMethod.DELETE])
    async def delete_collection(self, request:Request,response:Response,collection_name:str,cost:Annotated[FileCost,Depends(FileCost)],autPermission:AuthPermission=Depends(get_auth_permission)):
        """Delete all results and delete all enqueued job matching the collection_name filtered by the task_name """

        # fetch all queued job and result filter by the task_name

        async with self.session.delete() as response:
            ...
        
        # abort_queued job and delete result
        # return a list of FileMeta so i can refund
            
    @UseLimiter('1/minutes')
    @UsePipe(ArqJobIdPipe)
    @UseHandler(CostHandler,ArqHandler,ProxyRestGatewayHandler)
    @UseGuard(ArqDataTaskGuard(ArqDataTaskConstant.FILE_DATA_TASK))
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @BaseHTTPRessource.HTTPRoute('/docs/{job_id}',methods=[HTTPMethod.DELETE])
    async def delete_documents(self, request:Request,response:Response,cost:Annotated[FileCost,Depends(FileCost)],autPermission:AuthPermission=Depends(get_auth_permission)):
        """Delete result and the point associated with the job_id filtered by the task_name """

        # fetch the collection name using the result
        async with self.session.delete() as response:
            ...
        
        # return a list of FileMeta so we can refund
       

    @BaseHTTPRessource.HTTPRoute('/{collection_name}',methods=[HTTPMethod.GET])
    async def get_all_collection(self,request:Request,response:Response):
        ...
