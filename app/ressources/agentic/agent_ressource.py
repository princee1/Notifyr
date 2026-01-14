from typing import Annotated, Type
from fastapi import Body, Depends, Request, Response,status
from pydantic import ConfigDict
from app.classes.auth_permission import AuthPermission, Role
from app.container import InjectInMethod
from app.decorators.guards import LLMProviderGuard
from app.decorators.handlers import AgenticHandler, AsyncIOHandler, MotorErrorHandler, PydanticHandler, ServiceAvailabilityHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.permissions import AdminPermission, AgentPermission, JWTRouteHTTPPermission
from app.decorators.pipes import DocumentFriendlyPipe, MerchantPipe, MiniServiceInjectorPipe
from app.definition._cost import DataCost
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, Throttle, UseGuard, UseHandler, UseInterceptor, UseLimiter, UsePermission, UsePipe, UseRoles, UseServiceLock
from app.definition._service import StateProtocol
from app.depends.funcs_dep import get_profile
from app.errors.llm_error import LLMModelMaxTokenExceededError, LLMModelNotPermittedError, LLMProviderDoesNotExistError
from app.manager.broker_manager import Broker
from app.depends.dependencies import get_auth_permission
from app.manager.merchant_manager import Merchant
from app.models.agents_model import AgentModel
from app.services  import MongooseService
from app.services.agent.remote_agent_service import RemoteAgentMiniService
from app.utils.constant import CostConstant, LLMProviderConstant
from app.utils.helper import subset_model
from app.services  import RemoteAgentService
from app.models.llm_model import LLMProfileModel


base_attr = {'id','revision_id','created_at','last_modified','version'}


@HTTPRessource('prompt-playground')
class PromptPlaygroundRessource(BaseHTTPRessource):
    pass


@PingService([MongooseService])
@UseServiceLock(MongooseService,lockType='reader',check_status=False)
@UseRoles([Role.ADMIN])
@UseHandler(ServiceAvailabilityHandler,AsyncIOHandler,MotorErrorHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('agents')
class AgentsRessource(BaseHTTPRessource):
    
    UpdateAgentModel:Type[AgentModel] = subset_model(AgentModel,f'Update{AgentModel.__name__}',__config__=ConfigDict(extra="forbid"),exclude=set(AgentModel._unique_indexes).union(base_attr))

    class AgentInjectorPipe(MiniServiceInjectorPipe):
        def pipe(self, agent:str): return super().pipe(agent)
    
    def get_agent(agent:str):
        return agent

    @InjectInMethod()
    def __init__(self,remoteAgentService:RemoteAgentService,mongooseService:MongooseService): 
        super().__init__()
        self.remoteAgentService = remoteAgentService
        self.mongooseService = mongooseService
        self.provider_guard = LLMProviderGuard()
    
    @UsePermission(AdminPermission) 
    @UseInterceptor(DataCostInterceptor(CostConstant.AGENT_CREDIT))
    @UseHandler(AgenticHandler)
    @Throttle(normal=(200,80))
    @UsePipe(MerchantPipe())
    @UseGuard(LLMProviderGuard())
    @UsePipe(DocumentFriendlyPipe,before=False)
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
    async def create_agent(self,agentModel:AgentModel,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[DataCost,Depends(DataCost)],merchant:Annotated[Merchant,Depends(Merchant)], authPermission:AuthPermission=Depends(get_auth_permission)):
        
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
    @BaseHTTPRessource.HTTPRoute('/{agent}/',methods=[HTTPMethod.GET])
    async def read_agent(self,agent:str,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        return  await self.mongooseService.get(AgentModel,agent,True)
         
    @UsePermission(AdminPermission)
    @UsePipe(MerchantPipe(-1))
    @Throttle(normal=(200,80))
    @UseInterceptor(DataCostInterceptor(CostConstant.AGENT_CREDIT,'refund'))
    @UsePipe(DocumentFriendlyPipe,before=False)
    @BaseHTTPRessource.HTTPRoute('/{agent}/',methods=[HTTPMethod.DELETE])
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
    @UseHandler(PydanticHandler,AgenticHandler)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @BaseHTTPRessource.HTTPRoute('/{agent}/',methods=[HTTPMethod.PUT])
    async def update_agent(self,agent:str,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],body: dict = Body(...),authPermission:AuthPermission=Depends(get_auth_permission)):
        
        agentModel = await self.mongooseService.get(AgentModel,agent,True)
        agentUpdateModel = self.UpdateAgentModel.model_validate(body)
        await agentModel.update_profile(agentUpdateModel)

        await self.provider_guard.guard(agentModel=agentModel)
        
        await self.mongooseService.primary_key_constraint(agentModel,True)
        await self.mongooseService.exists_unique(agentModel,True)
        await agentModel.update_meta_profile()

        broker.propagate(StateProtocol(name=RemoteAgentService,to_build=True,to_destroy=True))
        return agentModel

    @UseRoles([Role.PUBLIC])        
    @UsePipe(DocumentFriendlyPipe,before=False)
    @BaseHTTPRessource.HTTPRoute('/all/',methods=[HTTPMethod.GET])
    async def get_all_agent(self,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        ...

    @UseRoles([Role.PUBLIC])        
    @UseLimiter('100/hour')
    @UseHandler(AgenticHandler)
    @Throttle(uniform=(30,60))
    @UsePermission(AgentPermission)
    @PingService([RemoteAgentService],is_manager=True,infinite_wait=True)
    @UseServiceLock(RemoteAgentService,lockType='reader',as_manager=True,miniLockType='reader')
    @UsePipe(MiniServiceInjectorPipe(RemoteAgentService,'agent'))
    @BaseHTTPRessource.HTTPRoute('/prompt/{agent}/',methods=[HTTPMethod.POST],mount=False)
    async def prompt_playground(self,request:Request,agent:Annotated[RemoteAgentMiniService,Depends(get_profile)], response:Response,profile:str=Depends(get_agent), authPermission:AuthPermission= Depends(get_auth_permission)):
        await agent.Prompt(
            
        )
