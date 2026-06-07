from typing import Annotated, Type
from fastapi import Body, Depends, Request, Response,status
from fastapi.responses import StreamingResponse
from pydantic import ConfigDict
from app.classes.auth_permission import AuthPermission, Role
from app.classes.embeddings import EmbeddingModel, EmbeddingWrapper
from app.container import InjectInMethod
from app.decorators.guards import LLMProviderGuard
from app.decorators.handlers import AgentHandler, AgenticHandler, LLMHandler, AsyncIOHandler, CostHandler, GrpcHandler, MotorErrorHandler, PydanticHandler, RedisHandler, ServiceAvailabilityHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.permissions import AdminPermission, AgentPermission, JWTRouteHTTPPermission
from app.decorators.pipes import DocumentFriendlyPipe, MerchantPipe, MiniServiceInjectorPipe
from app.definition._cost import DataCost
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, Throttle, UseGuard, UseHandler, UseInterceptor, UseLimiter, UsePermission, UsePipe, UseRoles, LockService
from app.definition._service import MiniStateProtocol, StateProtocol
from app.depends.class_dep import EmbeddingSimilarity
from app.depends.funcs_dep import get_profile
from app.errors.agent_error import AgentToolDoesNotExistError, SemanticAgentAlreadyExistError
from app.manager.broker_manager import Broker
from app.depends.dependencies import get_auth_permission, get_request_id
from app.manager.merchant_manager import Merchant
from app.models.odm.agents_model import AgentModel
from app.models.tools_model import ToolModel
from app.models.vector_model import QdrantEmbedRequestModel
from app.services  import MongooseService
from app.services.agent.llm_service import LLMService
from app.services.agent.remote_agent_service import RemoteAgentMiniService
from app.services.custom_service import CustomService
from app.utils.constant import AgenticConstant, CostConstant, LLMProviderConstant
from app.utils.helper import subset_model
from app.services  import RemoteAgentService
from app.models.odm.llm_model import LLMProfileModel


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
    
    async def semantic_lookup(self, request_id:str, issuer:str, agentModel:AgentModel,threshold:float):
        embedBody = QdrantEmbedRequestModel(query=agentModel.description,request_id=request_id,issuer=issuer)
        embedding = await self.remoteAgentService.request('POST',AgenticConstant.VECTOR_ROUTER('/embed/'),json=embedBody.model_dump())

        embedding:EmbeddingModel = EmbeddingModel(vector_id=agentModel.id,**embedding)
        wrapper = EmbeddingWrapper(embedding,threshold=threshold)
        for agent in await self.mongooseService.find_all(AgentModel):
            if agentModel.embeddings == None:
                continue
            if (coef:=EmbeddingWrapper.cosine(wrapper,EmbeddingWrapper(agentModel.embeddings)))>=wrapper.threshold:
                raise SemanticAgentAlreadyExistError(agentModel.id,agent.id,coef)

        return embedding

    async def lookup_tools(self,agentModel:AgentModel):
        tools = [t.id for t in await self.mongooseService.find_all(ToolModel)]
        diff = set(agentModel.tools).difference(tools)
        if len(diff) > 0:
            raise AgentToolDoesNotExistError(agentModel.id,diff)
    
    @UsePipe(MerchantPipe())
    @Throttle(normal=(200,80))
    @UsePermission(AdminPermission) 
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @UseInterceptor(DataCostInterceptor(CostConstant.AGENT_CREDIT))
    @UseHandler(LLMHandler,RedisHandler,CostHandler,AgentHandler)
    @LockService(LLMService,lockType='reader',as_manager=False)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
    async def create_agent(self,agentModel:AgentModel,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[DataCost,Depends(DataCost)],merchant:Annotated[Merchant,Depends(Merchant)],similarity:Annotated[EmbeddingSimilarity,Depends(EmbeddingSimilarity)], profile:str=Depends(get_agent), authPermission:AuthPermission=Depends(get_auth_permission)):
        await self.mongooseService.primary_key_constraint(agentModel,True)
        await self.mongooseService.exists_unique(agentModel,True)
        # TODO check cross needed agent
        await self.lookup_tools(agentModel)
        if similarity.mode == 'hard':
            embedding = await self.semantic_lookup(cost.request_id,cost.issuer,agentModel)
            agentModel.embeddings = embedding

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
        agent = await self.mongooseService.get(AgentModel,agent,True)
         
    @UsePipe(MerchantPipe(-1))
    @Throttle(normal=(200,80))
    @UsePermission(AdminPermission)
    @UseHandler(CostHandler,RedisHandler,AgentHandler)
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
    @UsePipe(DocumentFriendlyPipe,before=False)
    @UseHandler(PydanticHandler,LLMHandler,AgentHandler)
    @LockService(LLMService,lockType='reader',as_manager=False)
    @BaseHTTPRessource.HTTPRoute('/{agent}/',methods=[HTTPMethod.PUT])
    async def update_agent(self,agent:str,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],embeddingLookup:Annotated[EmbeddingSimilarity,Depends(EmbeddingSimilarity)],body: dict = Body(...),request_id:str=Depends(get_request_id),profile:str=Depends(get_agent),authPermission:AuthPermission=Depends(get_auth_permission)):
        
        agentModel = await self.mongooseService.get(AgentModel,agent,True)
        agentUpdateModel = self.UpdateAgentModel.model_validate(body)
        await agentModel.update_content(agentUpdateModel)

        await self.provider_guard.guard(agentModel=agentModel)
        
        await self.mongooseService.primary_key_constraint(agentModel,True)
        await self.mongooseService.exists_unique(agentModel,True)

        if 'description' in body and embeddingLookup.mode == 'hard':
            embedding = await self.semantic_lookup(request_id,authPermission['client_id'] , agentModel,embeddingLookup.threshold)
            agentModel.embeddings = embedding
        
        if 'tools' in body:
            await self.lookup_tools(agentModel)

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
        return await agent.Prompt()
    
    @UsePermission(AgentPermission)
    @UseHandler(LLMHandler,AgenticHandler,GrpcHandler)
    @BaseHTTPRessource.HTTPRoute('/stream/prompt/{agent}/',methods=[HTTPMethod.POST],mount=False)
    async def stream_prompt_playground(self,request:Request,response:Response,agent:Annotated[RemoteAgentMiniService,Depends(get_agent)]):
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