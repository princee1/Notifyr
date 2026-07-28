import asyncio
import functools
from typing import Any, Callable, Dict, List, NamedTuple, Self,Any, TypeVar, get_args
from pydantic import ValidationError
from app.classes.secrets import ChaCha20SecretsWrapper
from app.definition._agent import *
from app.classes.cost_definition import InsufficientCreditsError, InvalidPurchaseRequestError
from app.classes.prompt import PromptToken
from app.definition import _service
from app.definition._tool import Tool, dynamic_tool_selection, handle_tool_errors
from app.errors.agent_error import AgentNotAvailableError, AgentOnlyAsSubAgentError
from app.errors.llm_error import LLMProviderDoesNotExistError
from app.errors.service_error import BuildFailureError, BuildOkError, MiniServiceDoesNotExistsError
from app.grpc.agent_interceptor import AgentServerInterceptor, HandlerType
from app.models.odm.agents_model import *
from app.models.odm.outbound_model import HTTPOutboundModel
from app.prompt import system_prompt
from app.services.config_service import ConfigService
from app.services.cost_service import CostService
from app.services.custom_service import CustomService
from app.services.database.mongoose_service import AGENTIC_CREDS, MongooseService
from app.services.database.qdrant_service import QdrantService
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, LinkDep, MiniService, MiniServiceStore, Service, BaseMiniServiceManager, ServiceStatus
from app.services.database.redis_service import RedisService
from app.services.profile_service import  ProfileMiniService, ProfileService
from app.services.database.graphiti_service import GraphitiService
from app.services.reactive_service import ReactiveService
from app.services.vault_service import VaultService
from app.models.odm.tools_model import *
from app.tools.api_tool import APIControlTool, APIFetchTool
from app.tools.cache_tool import CacheTool
from app.tools.conversation_tool import ConversationTool
from app.tools.graph_tool import KnowledgeGraphTool,MemoryTool
from app.tools.mcp_tool import MCPTool
from app.tools.search_tool import SearchTool
from app.tools.vector_tool import VectorRagTool
from app.utils.constant import CostConstant, MongooseDBConstant
from app.utils.helper import slice_dict
from app.utils.toolbox import Mock
from .llm_service import LLMMiniService, LLMService
from .remote_agent_service import  RemoteAgentMiniService, RemoteAgentService
from concurrent import futures
import grpc
from app.grpc import agent_pb2_grpc,agent_pb2,agent_message
from langchain.agents.factory import create_agent
from langchain.tools import BaseTool, tool as tool_factory, ToolRuntime
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.store.mongodb import MongoDBStore
from langchain.agents.middleware import HumanInTheLoopMiddleware, ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain.messages import HumanMessage, SystemMessage,AIMessage,AIMessageChunk
from langchain_classic import hub
from langchain_core.rate_limiters import InMemoryRateLimiter
from app.classes import conversation
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

AVOID_RE_VALIDATE_BUILD_STATE = -100
AVOID_RECREATE_AGENT_BUILD_STATE = -435
RECREATE_MEMORY_BUILD_STATE = 895
RECREATE_AGENT_BUILD_STATE = 543
RECREATE_AGENT_WITH_OUTBOUND_BUILD_STATE=120
TOOL_RECREATE_BUILD_STATE = 890
AGENT_BUILD_CREATE_STATE = 4859

REACTIVE_TOKEN_COST = 'token_cost'
API_SECRET_KEY = 'API_KEY'

InterruptConfig = Dict

factory_include = ('temperature','model','timeout')
acceptable_service = {ServiceStatus.AVAILABLE,ServiceStatus.WORKS_ALMOST_ATT,ServiceStatus.PARTIALLY_AVAILABLE}
answer_exclude = {'token'}

C = TypeVar('C',BaseModel)


@MiniService(mirror=RemoteAgentMiniService,links=[LinkDep(LLMMiniService,to_build=True,build_state=AVOID_RE_VALIDATE_BUILD_STATE)])
class AgentMiniService(BaseMiniService):

    def __init__(self,
                configService:ConfigService,
                graphitiService:GraphitiService,
                qdrantService:QdrantService,
                mongooseService:MongooseService,
                llmMiniService:LLMMiniService,
                customService:CustomService,
                redisService:RedisService,
                agentService:'AgentService',
                agent_model:dict,
                toolModels:list[ToolModel],
                outboundServices:Dict[str,ProfileMiniService[HTTPOutboundModel]]={},
                clientServices:Dict[str,ProfileMiniService[BaseProfileModel]]={},
                __as_subagent__=False):
            
            self.depService = llmMiniService
            super().__init__(llmMiniService,str(agent_model['id']))
            self.mongooseService = mongooseService
            self.configService = configService
            self.graphitiService =  graphitiService
            self.redisService = redisService
            self.qdrantService = qdrantService
            self.customService = customService
            self.outboundServices = outboundServices
            self.clientServices = clientServices
            self.agent_model= agent_model
            self.agentService = agentService

            self.toolModels = []
            self.mcpServerModels:list[MCPServerToolModel] = []

            for tM in toolModels:
                if isinstance(tM,MCPServerToolModel):
                    self.mcpServerModels.append(tM)
                else:
                    self.toolModels.append(tM)

            self.__as_subagent__ = __as_subagent__

            for outbound in self.outboundServices.values():
                self.register(outbound)

            for client in self.clientServices.values():
                self.register(client)
            
            self.tools:Dict[str,Tool] = {}

    def verify_dependency(self):
        if self.depService.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError('LLM Provider is not available')
    
    def build(self, build_state = ...):
        try:
            if build_state == DEFAULT_BUILD_STATE:
                m = AgentValidationModel.model_validate(self.agent_model).model_dump()
                self.agent_model = AgentValidationModel.model_construct(**m)
        except ValidationError as e:
            raise BuildFailureError('Could not validate the agent model')
        
        hitl_config = {}
        tool_limits = []

        tools = self._init_tools(hitl_config,tool_limits)
        mcp_tools = self._init_mcp_tool()
        middleware = self._init_middleware(hitl_config,tool_limits,mcp_tools)
    
        prompt = system_prompt.SYSTEM_TEMPLATE(self.agent_model.system)
        self.prompt = SystemMessage([{'type':'text','text':prompt,"cache_control": {"type": "ephemeral"}}])
        self.agent = create_agent(
                model=self.chat_model,
                middleware=middleware,
                tools=tools,
                system_prompt=prompt,
                state_schema=NotifyrAgentState,
                context_schema=NotifyrContext,
                name=self.agent_name,
                checkpointer=self.agentService.checkpointer,
                store=self.agentService.store,
                )

        for id,service in self.outboundServices.items():
            if service.service_status not in acceptable_service:
                raise BuildOkError(f'OutboundService [{id}] does not have a valid state: {service.service_status}')
        
        for id,service in self.clientServices.items():
            if service.service_status not in acceptable_service:
                raise BuildOkError(f'OutboundService [{id}] does not have a valid state: {service.service_status}')
        return

    #########################################################################################################
    ############################                                          ###################################
    #########################################################################################################

    def _init_tools(self,hitl_config:dict,tool_limit:list,mcp_tools:list[MCPToolModel])->List[BaseTool]:
        tools = []
        for config in [*self.toolModels,*mcp_tools]:
            if hasattr(config,'outbound',None) and (outboundService:= self.outboundServices.get(config.outbound,None)) == None:
                continue
            if outboundService.service_status not in acceptable_service:
                continue
            if isinstance(config,VectorToolModel):
                tool = VectorRagTool(self.qdrantService,self.configService,self.customService,config)
            elif isinstance(config,CacheToolModel):
                tool = CacheTool(self.configService,self.redisService,config)
            elif isinstance(config,KnowledgeGraphToolModel,MemoryToolModel):
                cls = KnowledgeGraphTool if isinstance(config,KnowledgeGraphToolModel) else MemoryTool
                tool = cls(self.graphitiService,self.configService,config)
            elif isinstance(config,(APIToolModel,APIControlModel)):
                types = APIFetchTool if isinstance(config,APIToolModel) else APIControlTool
                tool = types(self.configService,outboundService)
            elif isinstance(config,SearchToolModel):
                tool = SearchTool(self.configService,self.qdrantService,self.customService)
            elif isinstance(config,MCPToolModel):
                tool = MCPTool(config,self.configService,self.redisService)
            elif isinstance(config,ConversationToolModel):
                tool = ConversationTool(self.configService,self.mongooseService,self.agentService.checkpointer)
            
            self.tools[tool.name] = tool 

            if (hitl:=tool.to_hitl()) != None:
                hitl_config.update(hitl)
            
            if (limit:=tool.to_limit())!= None:
                tool_limit.append(limit)
            
            if (retry:=tool.to_retry())!=None:
                tool_limit.append(retry)
            
            tool = tool_factory(tool.name,
                                infer_schema=False,
                                description=tool.description,
                                return_direct=tool.return_direct,
                                args_schema=tool.arg_schema,
                                extras={'__conditions__':tool.to_condition()}
                                )(tool)
            tools.append(tool)
                
        return tools

    def _init_middleware(self,interrupt_on,tool_limits:list[ToolCallLimitMiddleware[NotifyrAgentState,NotifyrContext]])->list[Callable|type]:
        middleware = []
        dynamic_middlewares = []

        if self.agent_model.rag == '':
            ...
        
        thread_guard = ThreadGuardFactory(self.agent_model)
        middleware.append(thread_guard)  # before agent

        middleware.append(guard_session_ends)  # before model

        if self.agent_model.callGuard != None:
            if self.agent_model.callGuard._limit:
                middleware.append(ModelCallLimitMiddleware( # before model
                    exit_behavior='error',
                    **self.agent_model.callGuard.model_dump(include=ModelCallGuardConfig.limit_keys,)),
                    )
            if self.agent_model.callGuard._retry:
                middleware.append(ModelRetryMiddleware( # wrap model
                    on_failure='error',
                    **self.agent_model.callGuard.model_dump(include=ModelCallGuardConfig.retry_keys,)),
                    )
        
        if self.agent_model.messageLimit != None:
            message_limiter = MessageLimitFactory(self.agent_model) #before model
            middleware.append(message_limiter)

        dynamic_system_prompt = DynamicSystemPromptFactory(...,...)
        middleware.append(dynamic_system_prompt) #wrap model
        middleware.append(handle_agent) #wrap model
        
        middleware.append(dynamic_tool_selection) #wrap tool call
        middleware.extend(tool_limits) #after model

        middleware.append(handle_tool_errors)

        # TODO add the LLMToolsSelector and Todo Middleware

        if interrupt_on:
            middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on)) #after model
                
        if self.agent_model.throttle:
            throttle = ThrottleFactory() # wrap model
            middleware.append(throttle)

        if isinstance(self.agent_model.model,str):
            purposed_models = ChatModelFactory(self.agent_model,self.depService.model,self.depService.credentials)
        else:
            purposed_models,dynamic_middlewares = DynamicChatModelFactory(self.agent_model,self.depService.model,self.depService.credentials)
        
        summaryInjector = SessionInjectionFactory(self.agent_model,self.depService.model)
        trimmer_middleware = MessageTrimmerFactory(self.agent_model,self.depService.model,purposed_models.summary)
        interrupt_middleware = SemanticInterruptParserFactory(self.agent_model,purposed_models.interrupt,self)
        marker_middleware = MarkerFactory(self.agent_model)
        
        middleware.append(interrupt_middleware) # before agent
        middleware.append(marker_middleware) # before model
        middleware.append(trimmer_middleware) # summary: before model / trim: wrap model
        
        middleware.append(filter_non_relevant_message) #wrap model
        middleware.append(summaryInjector) #wrap model
        
        middleware.extend(dynamic_middlewares) # wrap model
        middleware.append(inject_ai_turn) # after agent

        self.chat_model = purposed_models.basic
        return reversed(middleware)

    def _init_mcp_tool(self):
        mcpToolsModel:list[MCPToolModel] = []
        for mcp in self.mcpServerModels:
            if mcp.id not in self.agentService.mcp_tools:
                continue
            tools = self.agentService.mcp_tools[mcp.id]
            mcpToolsModel.extend([ MCPToolModel(mcp,t) for t in tools ])
        return mcpToolsModel
        
    def _init_subagent(self):
        ...
    
    #########################################################################################################
    ############################                                          ###################################
    #########################################################################################################
   
    async def invoke(self,thread:str,prompt:str,context:NotifyrContext,contents:list=[],mess_id:str=None):
        content_blocks = []
        content_blocks.append({'type':'text','text':prompt})
        content_blocks.extend(contents or [])
        add_kwargs:dict = {'__turn__':True}
        if contents:
            add_kwargs['__keep__'] = True
        message = HumanMessage(content_blocks=content_blocks,id=mess_id,additional_kwargs={'__turn__':True})

        config = {"configurable": {"thread_id": thread,"checkpoint_ns": self.agent_model.id}} 
        
        answer = conversation.Answer()
        answer['mode']='direct'
        answer['end'] = True

        response:AIMessage = await self.agent.ainvoke(message,config,context=context)
        if (usage:= response.usage_metadata):
            answer['token'] = conversation.Token(input_token=usage.get('input_tokens',0),output_token=usage.get('output_tokens',0))
            
        answer['reply_id'] = response.id
        answer['reasoning'] = [b for b in response.content_blocks if b["type"] == "reasoning"]
        answer['text'] = response.text
        answer['tool_calling'] = [slice_dict(tc,conversation.TOOL_CALLING_KEYS,'include') for tc in response.tool_calls]
        answer['invalid_tool_calling'] = [slice_dict(tc,conversation.invalid_tool_calling_keys,'include') for tc in response.invalid_tool_calls]
        return answer
        
    async def stream(self,thread: str,prompt: str,context: NotifyrContext,contents: list = [],mess_id: str = None,):
        content_blocks = [{'type': 'text', 'text': prompt}]
        content_blocks.extend(contents or [])
        add_kwargs:dict = {'__turn__':True}
        if contents:
            add_kwargs['__keep__'] = True
        message = HumanMessage(content_blocks=content_blocks,id=mess_id,additional_kwargs={'__turn__':True})

        config = {"configurable": {"thread_id": thread,"checkpoint_ns": self.agent_model.id}}
        async for chunk in self.agent.astream_events(message,config=config,context=context,version="v2",):
            answer = conversation.Answer()
            answer['mode'] ='stream'
            match chunk['event']:
                case 'on_chat_model_stream' | 'on_llm_stream':
                    response = chunk['data']['chunk']
                    answer['reply_id'] = response.id
                    answer['reasoning'] = [
                        b for b in getattr(response, 'content_blocks', [])
                        if b.get("type") == "reasoning"
                    ]
                    answer['text'] = getattr(response, 'text', '')
                    answer['tool_calling'] = [
                        slice_dict(tc, conversation.TOOL_CALLING_KEYS, 'include')
                        for tc in getattr(response, 'tool_calls', [])
                    ]
                    answer['invalid_tool_calling'] = [
                        slice_dict(tc, conversation.invalid_tool_calling_keys, 'include')
                        for tc in getattr(response, 'invalid_tool_calls', [])
                    ]
                case 'on_chat_model_end':
                    answer['end']=True
                    response = chunk['data']['output']
                    answer['reply_id'] = response.id
                    if usage := getattr(response, 'usage_metadata', None):
                        answer['token'] = conversation.Token(input_token=usage.get('input_tokens', 0),output_token=usage.get('output_tokens', 0),)
                case _:
                    continue

            yield answer
        
    async def completion(self,input:str,model:Type[C]|None=None,content:list=[])->C|str:
        message = [self.prompt,HumanMessage(input)]
        message.extend(content)
        if issubclass(model,BaseModel):
            chat_model = self.chat_model.with_structured_output(model,include_raw=True)
            response:AIMessage =  await chat_model.ainvoke(message)
            response
        else:
            response:AIMessage = await self.chat_model.ainvoke(message,)
            response

    async def batch(self,inputs:list[str]):
       async for response in self.chat_model.abatch_as_completed():
           yield 
    
    #########################################################################################################
    ############################                                          ###################################
    #########################################################################################################

    async def fetch_state(self):
        ...

    async def fetch_graph(self):
        ...
        
    async def fetch_interrupts(self):
        ...
    
    async def interrupts(self):
        ...
    
    #########################################################################################################
    ############################                                          ###################################
    #########################################################################################################

    def _verify_status(self,_raise=False):
        if self.service_status not in acceptable_service:
            raise AgentNotAvailableError(self.service_status,self.reason,self.miniService_id)
        if self.service_status != ServiceStatus.AVAILABLE:
            if _raise :
                raise AgentNotAvailableError(self.service_status,self.reason,self.miniService_id)
            return self.reason
        if not self.is_main_agent:
            raise AgentOnlyAsSubAgentError(self.miniService_id)
        
        return None

    #########################################################################################################
    ############################                                          ###################################
    #########################################################################################################
    @property
    def is_main_agent(self):
        return self.agent_model.type == 'main-agent'

    @property
    def agent_name(self)->str:
        return f"agent:{self.agent_model.alias}#{self.agent_model.id}"

@Service(is_manager=True,mirror=RemoteAgentService,links=[
    LinkDep(ProfileService,to_build=True,build_state=RECREATE_AGENT_WITH_OUTBOUND_BUILD_STATE),
    LinkDep(LLMService,to_build=True,build_state=AVOID_RE_VALIDATE_BUILD_STATE),
    LinkDep(MongooseService,to_build=True,build_state=RECREATE_MEMORY_BUILD_STATE),
    ])
class AgentService(BaseMiniServiceManager[AgentMiniService],agent_pb2_grpc.AgentServicer):

    @staticmethod
    def ErrorHandler(function:Callable):
        """
        This is a decorator that acts as exception handler, method for the grpc communication will have to be decorated
        by this to handle error found in their implementation
        
        :param function: The function to decorate
        :type function: Callable
        """

        @functools.wraps(function)
        async def handler(self:Self,request:Any|list[Any],context):
            try:
                async with self.lock('reader',None):
                    if self.service_status not in acceptable_service:
                        raise AgentNotAvailableError(self.service_status,self.reason,None)
                    return await function(self,request,context)

            except AgentNotAvailableError as e:
                context.abort(grpc.StatusCode.UNAVAILABLE,)
            
            except AgentInputFormatNotSupportedError as e:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT,...)

            except AgentOnlyAsSubAgentError as e:
                context.abort(grpc.StatusCode.UNAVAILABLE,...)
            
            except AgentContextDoesNotExistError as e:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT,)

            except AgentMessageLimitExceededError as e:
                context.abort(...,...)
            
            except AgentSessionAlreadyEndedError as e:
                context.abort(...,...)
            
            except AgentThreadBlockedError as e:
                context.abord(...,...)
            
            except ModelCallLimitExceededError as e:
                context.abort(...,...)
            
            except AgentModelRetryExceedError as e:
                context.abort(...,...)

            except MiniServiceDoesNotExistsError as e:
                context.abort(grpc.StatusCode.NOT_FOUND,f'Agent @ {e.miniService_id} does not exist')
            
            except InvalidPurchaseRequestError as e:
                context.abort(grpc.StatusCode.UNAVAILABLE,)
            
            except InsufficientCreditsError as e:
                context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED,f"Credit not suffisant. Current Balance: {e.current_balance} - Cost: {e.purchase_cost}")

        return handler

    #########################################################################################################
    ############################                                          ###################################
    #########################################################################################################

    @ErrorHandler
    async def Prompt(self, request, context):
        request = agent_message.PromptRequest.from_proto(request)
        async with self.MiniServiceStore.lock(request.agent) as agent:
            reason:str|None = agent._verify_status()
            contents = [conversation.ContentBlock.exports(c.mode,c.type,c.value,c.mime) for c in request.blocks]
            _context = create_context(request)
            answer = await agent.invoke(request.thread,request.prompt,_context,contents,request.mess_id)
            self.purchase_token(request_id=answer['id'],issuer=request.user,agent=request.agent,**answer['token'])
            return agent_message.PromptAnswer(agent=request.agent,reason =reason,**slice_dict(answer,answer_exclude,'exclude')).to_proto()

    @ErrorHandler
    async def PromptStream(self, request, context):
        request = agent_message.PromptRequest.from_proto(request)
        async with self.MiniServiceStore.lock(request.agent) as agent:
            reason:str|None = agent._verify_status()
            contents = [conversation.ContentBlock.exports(c.mode,c.type,c.value,c.mime) for c in request.blocks]
            _context = create_context(request,'stream')
            async for answer in agent.stream(request.thread,request.prompt,_context,contents,request.mess_id):
                yield agent_message.PromptAnswer(agent=request.agent,reason =reason,**slice_dict(answer,answer_exclude,'exclude')).to_proto()
                asyncio.sleep(0.2)
            self.purchase_token(request_id=answer['reply_id'],issuer=request.user,agent=request.agent,**answer['token'])

    @ErrorHandler
    async def StreamPrompt(self, request_iterator, context):
        prompt = ''
        async for request in request_iterator:
            request = agent_message.PromptRequest.from_proto(request)
            prompt += request.prompt
        
        async with self.MiniServiceStore.lock(request.agent) as agent:
            reason:str|None = agent._verify_status()
            _context = create_context(request)
            answer = await agent.invoke(request.thread,prompt,_context,mess_id=request.mess_id)
            self.purchase_token(request_id=answer['reply_id'],issuer=request.user,agent=request.agent,**answer['token'])
            return agent_message.PromptAnswer(agent=request.agent,reason =reason,**slice_dict(answer,answer_exclude,'exclude')).to_proto()

    @ErrorHandler
    async def S2SPrompt(self, request_iterator, context):
        async for request in request_iterator:
            request = agent_message.PromptRequest.from_proto(request)
            async with self.MiniServiceStore.lock(request.agent) as agent:
                    reason:str|None = agent._verify_status()
                    _context = create_context(request)
                    async for answer in agent.stream(request.thread,request.prompt,_context,mess_id=request.mess_id):
                        yield agent_message.PromptAnswer(agent=request.agent,reason = reason,**slice_dict(answer,answer_exclude,'exclude')).to_proto()
                        asyncio.sleep(0.1)
                    self.purchase_token(request_id=answer['reply_id'],issuer=request.user,agent=request.agent,**answer['token'])

    @ErrorHandler
    async def Completion(self,request,context):
        request = agent_message.PromptRequest.from_proto(request)
        async with self.MiniServiceStore.lock(request.agent) as service:
            reason:str|None = service._verify_status()
            contents = conversation.ContentBlock.exports()
            answer = await service.completion(request.prompt,contents,mess_id=request.mess_id)
            reply = agent_message.PromptAnswer(agent=request.agent,reason = reason,**slice_dict(answer,answer_exclude,'exclude')).to_proto()      
            self.purchase_token(request_id=answer['reply_id'],issuer=request.user,agent=request.agent,**answer['token'])
            return reply

    @Mock()
    @ErrorHandler
    async def S2SBatch(self,request_iterator,context):
        messages = []
        async for request in request_iterator:
            request = agent_message.PromptRequest.from_proto(request)
            messages.append(request)

        async with self.MiniServiceStore.lock(request.agent) as service:
            async for answer in service.batch():
                yield
        # append it as a list of message

    #########################################################################################################
    ############################                                          ###################################
    #########################################################################################################

    def __init__(self, configService: ConfigService,
                    vaultService:VaultService,
                    mongooseService:MongooseService,
                    llmProviderService:LLMService,
                    qdrantService:QdrantService,
                    reactiveService:ReactiveService,
                    profileService:ProfileService,
                    graphitiService:GraphitiService,
                    costService:CostService,
                    redisService:RedisService,
                    customService:CustomService) -> None:
        
        super().__init__()
        self.configService = configService
        self.mongooseService = mongooseService
        self.vaultService = vaultService
        self.llmProviderService = llmProviderService
        self.qdrantService = qdrantService
        self.graphitiService = graphitiService
        self.profileService = profileService
        self.reactiveService = reactiveService
        self.costService = costService
        self.redisService = redisService
        self.customService = customService

        self.mcp_client:MultiServerMCPClient = None
        self.mcp_tools=dict[str,List[BaseTool]] = {}

        self.MiniServiceStore = MiniServiceStore[AgentMiniService](self.name)
        self.tools_config:Dict[str,ToolModels] = {}

    def verify_dependency(self):
        ...

    def build(self, build_state=DEFAULT_BUILD_STATE):
        if build_state == DEFAULT_BUILD_STATE:
            secrets = self.vaultService.secrets_engine.read('internal','AGENTIC')

            if API_SECRET_KEY not in secrets:
                raise BuildFailureError(f'No Internal {API_SECRET_KEY} between the agentic server and the worker process found, cannot connect')
            
            self._agentic_key = ChaCha20SecretsWrapper(secrets[API_SECRET_KEY])
            self.reactive_subject = self.reactiveService.create_subject(REACTIVE_TOKEN_COST,'Normal',REACTIVE_TOKEN_COST,'message')

        if build_state == DEFAULT_BUILD_STATE or build_state == RECREATE_MEMORY_BUILD_STATE:
            self.checkpointer = MongoDBSaver(self.mongooseService.client_store.get_client(AGENTIC_CREDS,'sync'),
                                        MongooseDBConstant.DATABASE_NAME,
                                        MongooseDBConstant.CHAT_COLLECTION,
                                        MongooseDBConstant.CHAT_WRITE_COLLECTION,
                                        )

            self.store = MongoDBStore(self.mongooseService.client_store.get_collection(
                AGENTIC_CREDS,
                MongooseDBConstant.STORE_COLLECTION,
                'sync'))

        if build_state == DEFAULT_BUILD_STATE or build_state == TOOL_RECREATE_BUILD_STATE:
            self.tools_config.clear()
            for T in get_args(ToolModels):
                for t in self.mongooseService.sync_find(MongooseDBConstant.TOOL_COLLECTION,T,return_model=True,as_subset_model=True,filter_out=True):
                    self.tools_config[t.id] = t
        
        if  (build_state == DEFAULT_BUILD_STATE and self.CONTEXT == 'async') or build_state == AGENT_BUILD_CREATE_STATE:
            models:list[dict] = self.mongooseService.sync_find(MongooseDBConstant.AGENT_COLLECTION,AgentModel)
            counter = self.StatusCounter(len(models))
            self.MiniServiceStore.clear()

            for model in models:
                try:
                    agent = self._create_agent(model)
                    agent._builder(_service.BaseMiniService.QUIET_MINI_SERVICE,build_state,self.CONTAINER_LIFECYCLE_SCOPE)
                    counter.count(agent)
                    self.MiniServiceStore.add(agent)
                except LLMProviderDoesNotExistError as e:
                    continue
                except MiniServiceDoesNotExistsError as e:
                    continue
                            
            return super().build(counter, build_state)
    
    #########################################################################################################
    ############################                                          ###################################
    #########################################################################################################

    async def serve(self):
        interceptor = AgentServerInterceptor(self.AgenticAPIKey, {
            '/agent.Agent/Prompt': HandlerType.ONE_ONE,
            '/agent.Agent/PromptStream': HandlerType.ONE_MANY,
            '/agent.Agent/StreamPrompt': HandlerType.MANY_ONE,
            '/agent.Agent/S2SPrompt': HandlerType.MANY_MANY,
            '/agent.Agent/Completion':HandlerType.ONE_ONE,
            '/agent.Agent/S2SBatch':HandlerType.MANY_MANY,
        })
        self.server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=25),interceptors=(interceptor,))
        agent_pb2_grpc.add_AgentServicer_to_server(self,self.server)
        port = self.server.add_insecure_port('0.0.0.0:50051')
        await self.server.start()
    
    async def stop_grpc(self):
        await self.server.stop()
        await self.server.wait_for_termination()
    
    #########################################################################################################
    ############################                                          ###################################
    #########################################################################################################

    def subscribe_token(self,on_next:Callable[[Any],None],on_complete:Callable[[],None],on_error:Callable[[Exception],None]=None):
        return self.reactiveService.subscribe(REACTIVE_TOKEN_COST,on_next=on_next,on_completed=on_complete,on_error=on_error)

    def purchase_token(self,input_token:int,output_token:int,request_id:str,issuer:str,agent:str):
        promptToken = PromptToken(input=input_token,output=output_token,request_id=request_id,issuer=issuer,agent=agent)
        self.reactive_subject.on_next(promptToken)

    def complete_purchase(self):
        self.reactive_subject.on_completed()

    #########################################################################################################
    ############################                                          ###################################
    #########################################################################################################
   
    def _create_agent(self, model):
        provider_id = model['provider']
        provider = self.llmProviderService.MiniServiceStore.get(provider_id)

        tools:list[str] = model['tools']
        outboundServices = set()
        clientServices = set()

        agentTools = []

        for t in tools:
            if t not in self.tools_config:
                continue
            t = self.tools_config[t]
            if isinstance(t,(APIControlModel,APIToolModel)):
                if t.outbound:
                    outboundServices.add(t.outbound)
            if isinstance(t,SearchToolModel):
                ...
            agentTools.append(t)
                    
        outboundServices = slice_dict(self.profileService.MiniServiceStore._store_,outboundServices,'include',True)
        clientServices =  slice_dict(self.profileService.MiniServiceStore._store_,clientServices,'include',True)

        return AgentMiniService(
                    self.configService,
                    self.graphitiService,
                    self.qdrantService,
                    self.mongooseService,
                    provider,
                    self.customService,
                    self.redisService,
                    model,
                    self,
                    agentTools,
                    outboundServices,
                    clientServices
                )
        
    async def init_mcp_server(self):
        mcp_connections = {}
        stateful = []
        stateless = []
        for id,t in filter(lambda t:isinstance(t,MCPServerToolModel),self.tools_config.items()):
            t:MCPServerToolModel =t
            connection = t.langchain_config
            if t.session_mode == 'stateful':
                stateful.append(id)
            else:
                stateless.append(id)

            outboundService:ProfileMiniService[HTTPOutboundModel]=self.profileService.MiniServiceStore._store_.get(t.outbound,None)
            if not (t.authType !=None  and outboundService!= None):
                continue

            credentials = outboundService.credentials.to_plain()
            if t.authType == 'auth' and 'auth' in credentials:
                connection['auth'] = credentials['auth']
            else:
                connection['headers'] = {}
                if t.headers:
                    connection['headers'].update(t.headers)
                if 'headers' in credentials:
                    connection['headers'].update(credentials['headers'])

            mcp_connections[id] = connection
        
        self.mcp_client = MultiServerMCPClient(mcp_connections)
        self.mcp_tools.clear()

        for id in stateful:
            async with self.mcp_client.session(id) as session:
                tools = await load_mcp_tools(session)
                self.mcp_tools[id] = tools
        
        for id in stateless:
            tools = await self.mcp_client.get_tools()
            self.mcp_tools[id] = tools

    async def async_verify_dependency(self):
        await self.init_mcp_server()
    
    #########################################################################################################
    ############################                                          ###################################
    #########################################################################################################

    @property
    def AgenticAPIKey(self)->str:
        return self._agentic_key.to_plain()
    
def create_context(request:agent_message.PromptRequest,mode:Mode='direct'):
    _context = request.context
    if not _context:
        raise AgentContextDoesNotExistError
    return NotifyrContext(_context.request_id,
                          _context.session_id,
                          _context.channel,
                          mode,
                          _context.user,
                          _context.auth,
                          _context.save)
