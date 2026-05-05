import asyncio
import functools
from typing import Any, Callable, Dict, List, Self,Any
from fastapi import HTTPException
from pydantic import ValidationError
from app.classes.agents import ChatAgentFactory
from app.classes.cost_definition import InsufficientCreditsError, InvalidPurchaseRequestError
from app.classes.prompt import PromptToken
from app.definition import _service
from app.errors.service_error import BuildFailureError, MiniServiceDoesNotExistsError
from app.grpc.agent_interceptor import AgentServerInterceptor, HandlerType
from app.models.odm.agents_model import *
from app.prompt import agents_prompt
from app.services.config_service import ConfigService
from app.services.cost_service import CostService
from app.services.custom_service import CustomService
from app.services.database.mongoose_service import MongooseService
from app.services.database.qdrant_service import QdrantService
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, LinkDep, MiniService, MiniServiceStore, Service, BaseMiniServiceManager, ServiceStatus
from app.services.database.redis_service import RedisService
from app.services.mini.outbound.http_outbound_service import HTTPOutboundMiniService
from app.services.profile_service import  ProfileMiniService, ProfileService
from app.services.database.graphiti_service import GraphitiService
from app.services.reactive_service import ReactiveService
from app.services.vault_service import VaultService
from app.models.tools_model import *
from app.tools.api_tool import APIControlTool, APIFetchTool
from app.tools.cache_tool import CacheTool
from app.tools.conversation_tool import ConversationTool
from app.tools.graph_tool import KnowledgeGraphTool,MemoryTool
from app.tools.mcp_tool import MCPTool
from app.tools.search_tool import SearchTool
from app.tools.vector_tool import VectorRagTool
from app.utils.constant import CostConstant, MongooseDBConstant
from .llm_provider_service import LLMProviderMiniService, LLMProviderService
from .remote_agent_service import  RemoteAgentMiniService, RemoteAgentService
from concurrent import futures
import grpc
from app.grpc import agent_pb2_grpc,agent_pb2,agent_message
from langchain.agents.factory import create_agent
from langchain.tools import tool as tool_factory, ToolRuntime
from langgraph.checkpoint.mongodb import MongoDBSaver
from langchain.messages import SystemMessage, HumanMessage


AVOID_RE_VALIDATE_BUILD_STATE = -100
AVOID_RECREATE_AGENT_BUILD_STATE = -435

REACTIVE_TOKEN_COST = 'token_cost'

factory_include = ('temperature','model','timeout')

@MiniService(mirror=RemoteAgentMiniService,links=[LinkDep(LLMProviderMiniService,to_build=True,build_state=AVOID_RE_VALIDATE_BUILD_STATE)])
class AgentMiniService(BaseMiniService):

    def __init__(self,
                configService:ConfigService,
                graphitiService:GraphitiService,
                qdrantService:QdrantService,
                mongooseService:MongooseService,
                llmProviderMService:LLMProviderMiniService,
                customService:CustomService,
                redisService:RedisService,
                agent_model:dict,
                checkpointer:MongoDBSaver,
                outboundServices:Dict[str,HTTPOutboundMiniService]={}):
            
            self.depService = llmProviderMService
            super().__init__(llmProviderMService,str(agent_model['id']))
            self.mongooseService = mongooseService
            self.configService = configService
            self.graphitiService =  graphitiService
            self.redisService = redisService
            self.qdrantService = qdrantService
            self.customService = customService
            self.outboundServices = outboundServices
            self.agent_model=agent_model
            self.checkpointer = checkpointer

            for outbound in self.outboundServices.values():
                self.register(outbound)

            self.executors = {}
    
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

        self.chat_model = ChatAgentFactory(self.agent_model,self.depService.model,self.depService.credentials)
        tools = self._init_tools()
        middleware = self._init_middleware()
        prompt = agents_prompt.SYSTEM_PROMPT(self.agent_model.system)
        prompt = SystemMessage([{'type':'text','text':prompt,"cache_control": {"type": "ephemeral"}}])
        
        self.agent = create_agent(
                model=self.chat_model,
                middleware=middleware,
                tools=tools,
                system_prompt=prompt,
                name=self.agent_name,
                checkpointer=self.checkpointer
            )
        return
    
    def _init_tools(self)->list:
        tools = []
        for model in self.agent_model.tools:
            if isinstance(model,VectorToolModel):
                tool = VectorRagTool(self.qdrantService,self.configService,self.customService,model)
            elif isinstance(model,CacheToolModel):
                tool = CacheTool(self.configService,self.qdrantService,self.redisService,)
            elif isinstance(model,KnowledgeGraphToolModel):
                tool = KnowledgeGraphTool(self.graphitiService,self.configService,self.customService,self.qdrantService)
            elif isinstance(model,(APIToolModel,APIControlModel)):
                outboundService = self.outboundServices.get(model.outbound_id,None)
                if not outboundService:
                    continue
                types = APIFetchTool if isinstance(model,APIToolModel) else APIControlTool
                tool = types(self.configService,outboundService)
            elif isinstance(model,SearchToolModel):
                tool = SearchTool(self.configService,self.qdrantService,self.customService)
            elif isinstance(model,MCPToolModel):
                tool = MCPTool(self.configService)
            elif isinstance(model,MemoryToolModel):
                tool = MemoryTool(self.configService,self.graphitiService)
            elif isinstance(model,ConversationToolModel):
                tool = ConversationTool(self.configService,self.mongooseService)

            tool = tool_factory(tool.name,tool,description=tool.description,return_direct=tool.return_direct)
            tools.append(tool)
        
        return tools

    def _init_middleware(self):
        ...
            
    async def invoke(self,thread:str,prompt:str):
        config = {"configurable": {"thread_id": thread,"checkpoint_ns": self.agent_model.id}} 
        message = [{'role':'user','content':prompt}]
        response = await self.agent.ainvoke(message,config)
        
    async def stream(self,thread:str,prompt:str):
        config = {"configurable": {"thread_id": thread,"checkpoint_ns": self.agent_model.id}} 
        message = [{'role':'user','content':prompt}]

        async for chunk in self.agent.astream(message,config):
            yield
        
    async def completion(self,):
        await self.chat_model.ainvoke()

    @property
    def agent_name(self)->str:
        return f"agent:{self.agent_model.id}#{self.agent_model.id}"

@Service(is_manager=True,links=[LinkDep(LLMProviderService,to_build=True,build_state=AVOID_RE_VALIDATE_BUILD_STATE)],mirror=RemoteAgentService)
class AgentService(BaseMiniServiceManager,agent_pb2_grpc.AgentServicer):

    @staticmethod
    def Error_Handler(function:Callable):
        """
        This is a decorator that acts as exception handler, method for the grpc communication will have to be decorated
        by this to handle error found in their implementation
        
        :param function: The function to decorate
        :type function: Callable
        """

        @functools.wraps(function)
        async def handler(self:Self,request:Any|list[Any],context):
            try:
                return await function(self,request,context)
            except MiniServiceDoesNotExistsError as e:
                context.abort(grpc.StatusCode.NOT_FOUND,
                              f'Agent @ {e.miniService_id} does not exist')
            
            except InvalidPurchaseRequestError as e:
                context.abort(grpc.StatusCode.UNAVAILABLE)
            
            except InsufficientCreditsError as e:
                context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED,
                              f"Credit not suffisant. Current Balance: {e.current_balance} - Cost: {e.purchase_cost}")

        return handler

    @Error_Handler
    async def Prompt(self, request, context):
        request = agent_message.PromptRequest.from_proto(request)
        async with self.statusLock.reader as lock:
            service = self.MiniServiceStore.get(request.agent)
            async with service.statusLock.reader as l:
               
                await service.invoke()

                reply = agent_message.PromptAnswer()
                reply = reply.to_proto()
                
                self.purchase_token()
                return reply

    @Error_Handler
    async def PromptStream(self, request, context):
        request = agent_message.PromptRequest.from_proto(request)

        async with self.statusLock.reader as lock:
            service = self.MiniServiceStore.get(request.agent)
            async with service.statusLock.reader as l:

                async for response in service.stream():                    
                    reply = agent_message.PromptAnswer()
                    reply = reply.to_proto()
                    self.purchase_token()

                    yield reply
                    asyncio.sleep(0.2)

    @Error_Handler
    async def StreamPrompt(self, request_iterator, context):
        
        streams = []
        async for request in request_iterator:
            request = agent_message.PromptRequest.from_proto(request)
            streams.append(streams)

        async with self.statusLock.reader as lock:
            service = self.MiniServiceStore.get(request.agent)

            async with service.statusLock.reader as l:
                await service.invoke()

                reply = agent_message.PromptAnswer()         
                reply = reply.to_proto()

                self.purchase_token()
                return reply

    @Error_Handler
    async def S2SPrompt(self, request_iterator, context):
        async for request in request_iterator:
            request = agent_message.PromptRequest.from_proto(request)

            async with self.statusLock.reader as lock:
                service = self.MiniServiceStore.get(request.agent)

                async with service.statusLock.reader as l:
                    reply = agent_message.PromptAnswer()
                    reply = reply.to_proto()

                    self.purchase_token()
                    yield reply
                    asyncio.sleep(0.1)

    @Error_Handler
    async def Completion(self,context):
        ...

    def verify_auth(self,token:str)->bool:
        if self.auth_header != token:
            raise HTTPException(status_code=401,detail="Unauthorized")

    def __init__(self, configService: ConfigService,
                    vaultService:VaultService,
                    mongooseService:MongooseService,
                    llmProviderService:LLMProviderService,
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

        self.MiniServiceStore = MiniServiceStore[AgentMiniService](self.name)

    def subscribe_token(self,on_next:Callable[[Any],None],on_complete:Callable[[],None],on_error:Callable[[Exception],None]=None):
        return self.reactiveService.subscribe(
            REACTIVE_TOKEN_COST,
            on_next=on_next,
            on_completed=on_complete,
            on_error=on_error
        )

    def purchase_token(self,input_token:int,output_token:int,request_id:str,issuer:str,agent:str):
        promptToken = PromptToken(
            input=input_token,
            output=output_token,
            request_id=request_id,
            issuer=issuer,
            agent=agent
            )
        self.reactive_subject.on_next(promptToken)

    def complete_purchase(self):
        self.reactive_subject.on_completed()

    def filter_outbound_agentic(self,outbound_id:str):
        ...

    def build(self, build_state=...):
        if build_state == DEFAULT_BUILD_STATE:
            secrets = self.vaultService.secrets_engine.read('internal-api','AGENTIC')

            if 'API_KEY' not in secrets:
                raise BuildFailureError('No Internal API_KEY between the agentic server and the worker process found, cannot connect')
            
            self.auth_header = secrets['API_KEY']

            self.reactive_subject = self.reactiveService.create_subject(
                name=REACTIVE_TOKEN_COST,
                type_='Normal',
                subject_id=REACTIVE_TOKEN_COST,
                sid_type='message'
            )

        self.checkpointer = MongoDBSaver(self.mongooseService.sync_client,
                                    MongooseDBConstant.DATABASE_NAME,
                                    MongooseDBConstant.CHAT_COLLECTION,
                                    MongooseDBConstant.CHAT_WRITE_COLLECTION,
                                    )

        models:list[dict] = self.mongooseService.sync_find(MongooseDBConstant.AGENT_COLLECTION,AgentModel)
        counter = self.StatusCounter(len(models))
        self.MiniServiceStore.clear()

        for model in models:
            try:
                provider_id = model['provider']
                provider = self.llmProviderService.MiniServiceStore.get(provider_id)

                agent = AgentMiniService(
                    self.configService,
                    self.graphitiService,
                    self.qdrantService,
                    self.mongooseService,
                    provider,
                    self.customService,
                    self.redisService,
                    model,
                    self.checkpointer
                )
                agent._builder(_service.BaseMiniService.QUIET_MINI_SERVICE,build_state,self.CONTAINER_LIFECYCLE_SCOPE)
                counter.count(agent)
                self.MiniServiceStore.add(agent)
            except MiniServiceDoesNotExistsError as e:
                continue
                    
        return super().build(counter, build_state)
    
    async def serve(self):
        if self.service_status != ServiceStatus.AVAILABLE:
            return

        interceptor = AgentServerInterceptor(self.auth_header, {
            '/agent.Agent/Prompt': HandlerType.ONE_ONE,
            '/agent.Agent/PromptStream': HandlerType.ONE_MANY,
            '/agent.Agent/StreamPrompt': HandlerType.MANY_ONE,
            '/agent.Agent/S2SPrompt': HandlerType.MANY_MANY,
        })
        self.server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10),interceptors=(interceptor,))
        agent_pb2_grpc.add_AgentServicer_to_server(self,self.server)
        self.server.add_insecure_port('0.0.0.0:50051')
        await self.server.start()
        await self.server.wait_for_termination()
    
    async def stop_grpc(self):
        await self.server.stop()