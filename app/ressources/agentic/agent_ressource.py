import asyncio
from typing import Annotated, AsyncIterable, Optional, Type
from fastapi import Body, Depends, Header, Request, Response,status
from fastapi.responses import StreamingResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import ConfigDict
from app.classes.auth_permission import AuthPermission, ClientType, MustHaveWhen, Role
from app.classes.conversation import Message, Reply, Session, User
from app.classes.embeddings import EmbeddingModel, EmbeddingWrapper
from app.classes.mongo import MongoFindFilter
from app.container import InjectInMethod
from app.decorators.guards import LLMProviderGuard
from app.decorators.handlers import AgentHandler, AgenticHandler, DataSourceHandler, LLMHandler, AsyncIOHandler, CostHandler, GrpcHandler, MiniServiceHandler, MotorErrorHandler, PydanticHandler, RedisHandler, ServiceAvailabilityHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.permissions import AdminPermission, AgentPermission, ClientTypesPermission, JWTRouteHTTPPermission, MCPPermission
from app.decorators.pipes import DocumentFriendlyPipe, MerchantPipe, MiniServiceInjectorPipe, SanitizePathParameterPipe
from app.definition._cost import DataCost
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, Throttle, UseGuard, UseHandler, UseInterceptor, UseLimiter, UsePermission, UsePipe, UseRoles, LockService
from app.definition._service import MiniStateProtocol, StateProtocol
from app.depends.class_dep import EmbeddingSimilarity
from app.depends.variables import SourceMode,source_mode_query
from app.errors.agent_error import AgentDependencyError, AgentToolDoesNotExistError, SemanticAgentAlreadyExistError, SubAgentContainsSubAgentError
from app.errors.depends_error import DataSourceNotSupportedError
from app.manager.broker_manager import Broker
from app.depends.dependencies import get_auth_permission, get_request_id
from app.manager.merchant_manager import Merchant
from app.models.odm.agents_model import AgentModel, PromptPlaygroundModel
from app.models.odm.tools_model import SubAgentToolModel, ToolModel
from app.models.vector_model import QdrantEmbedRequestModel
from app.services  import MongooseService
from app.services.agent.llm_service import LLMService
from app.services.agent.remote_agent_service import RemoteAgentMiniService
from app.services.chat_service import ChatService, answer_to_reply, message_to_request
from app.services.config_service import ConfigService
from app.services.custom_service import CustomService
from app.services.database.mongoose_service import AGENTIC_CREDS
from app.utils.constant import AgenticConstant, CostConstant, LLMProviderConstant
from app.utils.helper import subset_model
from app.services  import RemoteAgentService
from app.models.odm.llm_model import LLMProfileModel
from app.classes.operation_id import MCPOperationID
from app.depends.variables import mcp_configuration


base_attr = {'id','revision_id','created_at','last_modified','version'}


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
    def __init__(self,remoteAgentService:RemoteAgentService,mongooseService:MongooseService,customService:CustomService,configService:ConfigService): 
        super().__init__()
        self.remoteAgentService = remoteAgentService
        self.mongooseService = mongooseService
        self.customService = customService
        self.configService = configService
        self.provider_guard = LLMProviderGuard()
    
    async def semantic_lookup(self, request_id:str, issuer:str, agentModel:AgentModel,threshold:float,agentModels:list[AgentModel]=None):
        embedBody = QdrantEmbedRequestModel(query=agentModel.description,request_id=request_id,issuer=issuer)
        embedding = await self.remoteAgentService.request('POST',AgenticConstant.VECTOR_ROUTER('/embed/'),json=embedBody.model_dump())

        embedding:EmbeddingModel = EmbeddingModel(vector_id=agentModel.id,**embedding)
        wrapper = EmbeddingWrapper(embedding,threshold=threshold)
        for agent in (agentModels or (await self.mongooseService.find_all(AgentModel))):
            if agentModel.embeddings == None:
                continue
            if (coef:=EmbeddingWrapper.cosine(wrapper,EmbeddingWrapper(agentModel.embeddings)))>=wrapper.threshold:
                raise SemanticAgentAlreadyExistError(agentModel.id,agent.id,coef)

        return embedding

    async def lookup_tools(self,agentModel:AgentModel,verify:bool=True):
        tools = []
        agents:set[str] = set() 
        for t in await self.mongooseService.find_all(ToolModel):
            tools.append(t.id)
            if not isinstance(t,SubAgentToolModel):
                continue
            if t.id in agentModel.tools and agentModel.type == 'sub-agent' and not self.configService.ALLOWED_TWO_LEVEL_SUBAGENT:
                raise SubAgentContainsSubAgentError(agentModel.id,t.id)
        
            agents.intersection_update(t.agents)

        if not verify:
            return agents
        
        diff = set(agentModel.tools).difference(tools)
        if len(diff) > 0:
            raise AgentToolDoesNotExistError(agentModel.id,diff)
        
        return agents
        # TODO make sure we do not have similar tools
    
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
        
        agentModels = await self.mongooseService.find_all(AgentModel)
        needed_agents = await self.lookup_tools(agentModel)

        if (diff_agents:=needed_agents.difference([a.id for a in agentModels])):
            raise AgentDependencyError(diff_agents,'needed')

        if similarity.mode == 'hard':
            embedding = await self.semantic_lookup(cost.request_id,cost.issuer,agentModel,similarity.threshold,agentModels)
            agentModel.embeddings = embedding

        merchant.safe_payment(
            None,
            None,
            agentModel.save
        )
        broker.propagate(StateProtocol(name=RemoteAgentService,to_build=True,to_destroy=True))
        return agentModel
    
    @UsePipe(DocumentFriendlyPipe,before=False)
    @UseHandler(MiniServiceHandler,DataSourceHandler)
    @UsePermission(AgentPermission(True),MCPPermission)
    @LockService(LLMService,lockType='reader',as_manager=False)
    @UsePipe(SanitizePathParameterPipe({},profile=True,agent=True))
    @LockService(RemoteAgentService,lockType='reader',as_manager=False)
    @UseRoles([Role.PUBLIC],options=[MustHaveWhen(Role.MCP,configuration=mcp_configuration)])
    @BaseHTTPRessource.HTTPRoute('/{agent:path}/',methods=[HTTPMethod.GET],to_mcp_tool=True,operation_id='read_agent_information')
    async def read_agent(self,agent:str,request:Request,response:Response,mongoFilter:Optional[MongoFindFilter],profile:str=Depends(get_agent),source:SourceMode=Depends(source_mode_query), authPermission:AuthPermission=Depends(get_auth_permission)):
        match source:
            case 'database':
                if agent != '':
                    return await self.mongooseService.get(AgentModel,agent,True)
                else:
                    agents = await self.mongooseService.find(AgentModel,mongoFilter.mapping,**mongoFilter.model_dump(exclude={'mapping'}))
                    agents = filter(lambda a: AgentPermission.predicate(a.id,authPermission),agents)
                    return list(agents)
            case 'memory':
                if agent != '':
                    async with self.remoteAgentService.MiniServiceStore.lock(agent) as service:
                        return service.agent_model
                else:
                    agents = []
                    async for a in self.remoteAgentService.MiniServiceStore.aiter(predicate=lambda a: AgentPermission.predicate(a.miniService_id,authPermission)):
                        agents.append(a.agent_model)
                    return agents
            case _:
                raise DataSourceNotSupportedError(source,['database','memory'])
         
    @UsePipe(MerchantPipe(-1))
    @Throttle(normal=(200,80))
    @UsePermission(AdminPermission)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @UseHandler(CostHandler,RedisHandler,AgentHandler)
    @LockService(LLMService,lockType='reader',as_manager=False)
    @UseInterceptor(DataCostInterceptor(CostConstant.AGENT_CREDIT,'refund'))
    @BaseHTTPRessource.HTTPRoute('/{agent}/',methods=[HTTPMethod.DELETE])
    async def delete_agent(self,agent:str,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[DataCost,Depends(DataCost)],merchant:Annotated[Merchant,Depends(Merchant)],profile:str=Depends(get_agent),authPermission:AuthPermission=Depends(get_auth_permission)):
        agentModel = await self.mongooseService.get(AgentModel,agent,True)

        agentModels = await self.mongooseService.find_all(AgentModel)
        toolModels = await self.mongooseService.find_all(ToolModel)
        agentTools = set([t.id for t in toolModels if isinstance(t,SubAgentToolModel) and (agentModel.id in t.agents)])

        for a in agentModels:
            if (intersection:=set(a.tools).intersection(agentTools)):
                raise AgentDependencyError(intersection,'affected')
        
        async def transaction():
            async with self.mongooseService.transaction(AGENTIC_CREDS,3,2) as (session,context):
                await self.mongooseService.delete(agentModel,session=session)
                for tool in filter(lambda tool: tool.id in agentTools,toolModels):
                    tool.agents = list(set(tool.agents).difference([agentModel.id]))
                    await tool.update_meta(session=session)

        merchant.safe_payment(
            None,
            None,
            transaction
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

    @Throttle(uniform=(30,60))
    @UseRoles([Role.AGENT,Role.ADMIN])
    @LockService(LLMService,lockType='reader',as_manager=False)
    @UsePipe(MiniServiceInjectorPipe(RemoteAgentService,'agent'))
    @UseHandler(LLMHandler,AgenticHandler,GrpcHandler,AgentHandler)
    @UseLimiter('100/hour',cost={'Admin':1,'User':3},key_func='private')
    @LockService(RemoteAgentService,lockType='reader',as_manager=True,miniLockType='reader')
    @UsePermission(ClientTypesPermission([ClientType.User,ClientType.Admin]),AgentPermission)
    @PingService([{'cls':RemoteAgentService,'kwargs':{'grpc':True}}],is_manager=True,infinite_wait=True)
    @BaseHTTPRessource.HTTPRoute('/prompt/{agent}/',methods=[HTTPMethod.POST],mount=False,response_model=Reply)
    async def prompt_playground(self,request:Request,agent:Annotated[RemoteAgentMiniService,Depends(get_agent)],prompt:PromptPlaygroundModel, response:Response,profile:str=Depends(get_agent),request_id:str = Depends(get_request_id),authPermission:AuthPermission= Depends(get_auth_permission)):
        message = Message(agent=agent,thread=authPermission['client_id'],**prompt.model_dump(exclude_none=True))
        user = User(authPermission['client_id'],'guest',None)
        session = Session(request_id,...,'live-chat',[])

        prompt_request = message_to_request(message,session,user)
        answer = await agent.Prompt(prompt_request)
        reply = answer_to_reply(answer)
        return reply
    
    @Throttle(uniform=(30,60))
    @UseRoles([Role.AGENT,Role.ADMIN])
    @UsePipe(MiniServiceInjectorPipe(RemoteAgentService,'agent'))
    @UseHandler(LLMHandler,AgenticHandler,GrpcHandler,AgentHandler)
    @UseLimiter('100/hour',cost={'Admin':1,'User':3},key_func='private')
    @LockService(RemoteAgentService,lockType='reader',as_manager=True,miniLockType='reader')
    @UsePermission(ClientTypesPermission([ClientType.User,ClientType.Admin]),AgentPermission)
    @PingService([{'cls':RemoteAgentService,'kwargs':{'grpc':True}}],is_manager=True,infinite_wait=True)
    @BaseHTTPRessource.HTTPRoute('/stream/prompt/{agent}/',methods=[HTTPMethod.POST],mount=False,response_class=EventSourceResponse)
    async def stream_prompt_playground(self,request:Request,response:Response,prompt:PromptPlaygroundModel,agent:Annotated[RemoteAgentMiniService,Depends(get_agent)],profile:str=Depends(get_agent),request_id:str = Depends(get_request_id),last_event_id: Annotated[int | None, Header()] = None,authPermission:AuthPermission= Depends(get_auth_permission))->AsyncIterable[ServerSentEvent]:
        message = Message(agent=agent,thread=authPermission['client_id'],**prompt.model_dump(exclude_none=True))
        user = User(authPermission['client_id'],'guest',None)
        session = Session(request_id,...,'live-chat',[])
        prompt_request = message_to_request(message,session,user)

        answers = await agent.PromptStream(prompt_request)
        async for i,answer in enumerate(answers):
            if i == 0:
                yield ServerSentEvent(raw_data=None,event='[OK]',comment="chat request ok")
                asyncio.sleep(0.05)

            reply = answer_to_reply(answer)
            yield ServerSentEvent(data=reply,event='[STREAM]',comment=f'streaming chat at {i}')
        
        yield ServerSentEvent(raw_data=None,event='[DONE]',comment='streaming done')
            
        