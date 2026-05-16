from typing import Annotated, Type
from fastapi import Body, Depends, Request, Response,status
from fastapi.responses import StreamingResponse
from pydantic import ConfigDict
from app.classes.auth_permission import AuthPermission, Role
from app.container import InjectInMethod
from app.decorators.guards import LLMProviderGuard
from app.decorators.handlers import AgenticHandler, LLMHandler, AsyncIOHandler, CostHandler, GrpcHandler, MotorErrorHandler, PydanticHandler, RedisHandler, ServiceAvailabilityHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.permissions import AdminPermission, AgentPermission, JWTRouteHTTPPermission
from app.decorators.pipes import DocumentFriendlyPipe, MerchantPipe, MiniServiceInjectorPipe
from app.definition._cost import DataCost
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, Throttle, UseGuard, UseHandler, UseInterceptor, UseLimiter, UsePermission, UsePipe, UseRoles, LockService
from app.definition._service import MiniStateProtocol, StateProtocol
from app.depends.funcs_dep import get_profile
from app.errors.llm_error import LLMModelMaxTokenExceededError, LLMModelNotPermittedError, LLMProviderDoesNotExistError
from app.manager.broker_manager import Broker
from app.depends.dependencies import get_auth_permission
from app.manager.merchant_manager import Merchant
from app.models.odm.agents_model import AgentModel
from app.services  import MongooseService
from app.services.agent.llm_service import LLMService
from app.services.agent.remote_agent_service import RemoteAgentMiniService
from app.services.custom_service import CustomService
from app.utils.constant import CostConstant, LLMProviderConstant
from app.utils.helper import subset_model
from app.services  import RemoteAgentService
from app.models.llm_model import LLMProfileModel


base_attr = {'id','revision_id','created_at','last_modified','version'}


@HTTPRessource('prompt-playground')
class PromptPlaygroundRessource(BaseHTTPRessource):
    pass


@UseRoles([Role.ADMIN])
@PingService([MongooseService])
@UsePermission(JWTRouteHTTPPermission)
@LockService(MongooseService,lockType='reader',check_status=False)
@UseHandler(ServiceAvailabilityHandler,AsyncIOHandler,MotorErrorHandler)
@HTTPRessource('agents')
class AgentsRessource(BaseHTTPRessource):
    
    UpdateAgentModel:Type[AgentModel] = subset_model(AgentModel,f'Update{AgentModel.__name__}',__config__=ConfigDict(extra="forbid"),exclude=set(AgentModel._unique_indexes).union(base_attr))

    class AgentInjectorPipe(MiniServiceInjectorPipe):
        def pipe(self, agent:str): return super().pipe(agent)
    
    def get_agent(agent:str):
        return agent

    @InjectInMethod()
    def __init__(self,remoteAgentService:RemoteAgentService,mongooseService:MongooseService,customService:CustomService): 
        super().__init__()
        self.remoteAgentService = remoteAgentService
        self.mongooseService = mongooseService
        self.customService = customService
        self.provider_guard = LLMProviderGuard()
    
    @UsePermission(AdminPermission) 
    @Throttle(normal=(200,80))
    @UsePipe(MerchantPipe())
    @UseGuard(LLMProviderGuard())
    @UseInterceptor(DataCostInterceptor(CostConstant.AGENT_CREDIT))
    @UseHandler(LLMHandler,RedisHandler,CostHandler)
    @LockService(LLMService,lockType='reader',as_manager=False)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
    async def create_agent(self,agentModel:AgentModel,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[DataCost,Depends(DataCost)],merchant:Annotated[Merchant,Depends(Merchant)],profile:str=Depends(get_agent), authPermission:AuthPermission=Depends(get_auth_permission)):
        
        await self.mongooseService.primary_key_constraint(agentModel,True)
        await self.mongooseService.exists_unique(agentModel,True)
        
        merchant.safe_payment(
            None,
            None,
            agentModel.save
        )

        broker.propagate(StateProtocol(name=RemoteAgentService,to_build=True,to_destroy=True))
        return agentModel

    @UseRoles([Role.PUBLIC])        
    @UsePermission(AgentPermission)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @LockService(LLMService,lockType='reader',as_manager=False)
    @BaseHTTPRessource.HTTPRoute('/{agent}/',methods=[HTTPMethod.GET])
    async def read_agent(self,agent:str,request:Request,response:Response,profile:str=Depends(get_agent),authPermission:AuthPermission=Depends(get_auth_permission)):
        return  await self.mongooseService.get(AgentModel,agent,True)
         
    @UsePipe(MerchantPipe(-1))
    @Throttle(normal=(200,80))
    @UsePermission(AdminPermission)
    @UseHandler(CostHandler,RedisHandler)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @LockService(LLMService,lockType='reader',as_manager=False)
    @UseInterceptor(DataCostInterceptor(CostConstant.AGENT_CREDIT,'refund'))
    @BaseHTTPRessource.HTTPRoute('/s/{agent}/',methods=[HTTPMethod.DELETE])
    async def delete_agent(self,agent:str,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[DataCost,Depends(DataCost)],merchant:Annotated[Merchant,Depends(Merchant)],profile:str=Depends(get_agent),authPermission:AuthPermission=Depends(get_auth_permission)):
        agentModel = await self.mongooseService.get(AgentModel,agent,True)

        merchant.safe_payment(
            None,
            None,
            self.mongooseService.delete,
            agentModel
        )
        broker.propagate(StateProtocol(name=RemoteAgentService,to_build=True,to_destroy=True))
        return agentModel

    @Throttle(uniform=(100,200))
    @UsePermission(AdminPermission)
    @UseHandler(PydanticHandler,LLMHandler)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @LockService(LLMService,lockType='reader',as_manager=False)
    @BaseHTTPRessource.HTTPRoute('/{agent}/',methods=[HTTPMethod.PUT])
    async def update_agent(self,agent:str,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],body: dict = Body(...),profile:str=Depends(get_agent),authPermission:AuthPermission=Depends(get_auth_permission)):
        
        agentModel = await self.mongooseService.get(AgentModel,agent,True)
        agentUpdateModel = self.UpdateAgentModel.model_validate(body)
        await agentModel.update_content(agentUpdateModel)

        await self.provider_guard.guard(agentModel=agentModel)
        
        await self.mongooseService.primary_key_constraint(agentModel,True)
        await self.mongooseService.exists_unique(agentModel,True)
        await agentModel.update_meta()

        broker.propagate(MiniStateProtocol(name=RemoteAgentService,to_build=True,to_destroy=True,id=agent))
        return agentModel

    @UseRoles([Role.PUBLIC])        
    @UsePipe(DocumentFriendlyPipe,before=False)
    @LockService(LLMService,lockType='reader',as_manager=False)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.GET])
    async def get_all_agent(self,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        ...

    @UseRoles([Role.PUBLIC])        
    @UseLimiter('100/hour')
    @Throttle(uniform=(30,60))
    @UsePermission(AgentPermission)
    @UseHandler(LLMHandler,AgenticHandler,GrpcHandler)
    @UsePipe(MiniServiceInjectorPipe(RemoteAgentService,'agent'))
    @PingService([{'cls':RemoteAgentService,'kwargs':{'grpc':True}}],is_manager=True,infinite_wait=True)
    @LockService(RemoteAgentService,lockType='reader',as_manager=True,miniLockType='reader')
    @LockService(LLMService,lockType='reader',as_manager=False)
    @BaseHTTPRessource.HTTPRoute('/prompt/{agent}/',methods=[HTTPMethod.POST],mount=False)
    async def prompt_playground(self,request:Request,agent:Annotated[RemoteAgentMiniService,Depends(get_agent)], response:Response,profile:str=Depends(get_agent), authPermission:AuthPermission= Depends(get_auth_permission)):
        stream = False
        if not stream:
            return await agent.Prompt()
        else:
            async def response_stream():
                replies = await agent.PromptStream()
                async for reply in replies:
                    ...
                    yield reply
            
            return StreamingResponse(
                content=response_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                    }
            )
            