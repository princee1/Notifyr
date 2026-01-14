import asyncio
from typing import Any, Callable
from fastapi import HTTPException
from pydantic import ValidationError
from app.classes.prompt import PromptToken
from app.definition import _service
from app.errors.service_error import BuildFailureError, MiniServiceDoesNotExistsError
from app.grpc.agent_interceptor import AgentServerInterceptor, HandlerType
from app.models.agents_model import AgentModel
from app.services.config_service import ConfigService
from app.services.database.mongoose_service import MongooseService
from app.services.database.qdrant_service import QdrantService
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, LinkDep, MiniService, MiniServiceStore, Service, BaseMiniServiceManager, ServiceStatus
from app.services.profile_service import ProfileService
from app.services.database.neo4j_service import Neo4JService
from app.services.reactive_service import ReactiveService
from app.services.vault_service import VaultService
from app.utils.constant import MongooseDBConstant
from app.utils.helper import subset_model
from .llm_provider_service import LLMProviderMiniService, LLMProviderService
from .remote_agent_service import RemoteAgentMiniService, RemoteAgentService
from concurrent import futures
import grpc
from app.grpc import agent_pb2_grpc,agent_pb2,agent_message



agent_validation_model = subset_model(AgentModel,'ValidationAgentModel')

AVOID_RE_VALIDATE_BUILD_STATE = -100

REACTIVE_TOKEN_COST = 'token_cost'

factory_include = ('temperature','model','timeout')

@MiniService(links=[LinkDep(LLMProviderMiniService,to_build=True,build_state=AVOID_RE_VALIDATE_BUILD_STATE)])
class AgentMiniService(BaseMiniService):
    ...
    """
    will register the tools
    and store the agent config
    graph of tools
    call the provider
    """
    def __init__(self,configService:ConfigService,llmProviderMService:LLMProviderMiniService,agent_model:AgentModel):
            self.depService = llmProviderMService
            self.agent_model=agent_model
            self.configService = configService
            super().__init__(llmProviderMService,str(agent_model.id))
    
    def verify_dependency(self):
        if self.depService.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError()
    
    def build(self, build_state = ...):
        try:
            if build_state == DEFAULT_BUILD_STATE:
                m = agent_validation_model.model_validate(self.agent_model).model_dump()
                self.agent_model = agent_validation_model.model_construct(**m)
            
            self.chat = self.depService.ChatAgentFactory(self.agent_model)
        except ValidationError as e:
            raise BuildFailureError('Could not validate the agent model')
    
    async def invoke(self):
        ...

    async def stream(self):
        ...

    async def reconstruct(self):
        ...
    

@Service(is_manager=True,links=[LinkDep(LLMProviderService,to_build=True,build_state=AVOID_RE_VALIDATE_BUILD_STATE)],mirror=RemoteAgentService)
class AgentService(BaseMiniServiceManager,agent_pb2_grpc.AgentServicer):

    async def Prompt(self, request, context):
        request = agent_message.PromptRequest.from_proto(request)
        reply = agent_message.PromptAnswer()
        reply.to_proto()
        return reply
        
    async def PromptStream(self, request, context):
        request = agent_message.PromptRequest.from_proto(request)

        for i in range(5):
            reply = agent_message.PromptAnswer()
            reply = reply.to_proto()
            yield reply
            asyncio.sleep(0.2)
            
    async def StreamPrompt(self, request_iterator, context):
        
        for request in request_iterator:
            request = agent_message.PromptRequest.from_proto(request)

        reply = agent_message.PromptAnswer()         
        reply = reply.to_proto()
        return reply

    async def S2SPrompt(self, request_iterator, context):
        for request in request_iterator:
            request = agent_message.PromptRequest.from_proto(request)

            asyncio.sleep(0.1)
            reply = agent_message.PromptAnswer()
            reply = reply.to_proto()
            yield reply

    def verify_auth(self,token:str)->bool:
        if self.auth_header != token:
            raise HTTPException(status_code=401,detail="Unauthorized")

    def __init__(self, configService: ConfigService,
                    vaultService:VaultService,
                    mongooseService:MongooseService,
                    remoteAgentService:RemoteAgentService,
                    llmProviderService:LLMProviderService,
                    qdrantService:QdrantService,
                    reactiveService:ReactiveService,
                    profileService:ProfileService,
                    neo4jService:Neo4JService) -> None:
        
        super().__init__()
        self.configService = configService
        self.mongooseService = mongooseService
        self.llmProviderService = llmProviderService
        self.remoteAgentService = remoteAgentService
        self.qdrantService = qdrantService
        self.vaultService = vaultService
        self.neo4jService = neo4jService
        self.profileService = profileService
        self.reactiveService = reactiveService

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

    def build(self, build_state=...):
        if build_state == DEFAULT_BUILD_STATE:
            secrets = self.vaultService.secrets_engine.read('internal-api','AGENTIC')

            if 'API_KEY' not in secrets:
                raise BuildFailureError()
            
            self.auth_header = secrets['API_KEY']

            self.reactive_subject = self.reactiveService.create_subject(
                name=REACTIVE_TOKEN_COST,
                type_='Normal',
                subject_id=REACTIVE_TOKEN_COST,
                sid_type='message'
            )

        models = self.mongooseService.sync_find(MongooseDBConstant.AGENT_COLLECTION,AgentModel)
        counter = self.StatusCounter(len(models))
        self.MiniServiceStore.clear()

        for model in models:
            try:
                provider_id = model.provider
                provider = self.llmProviderService.MiniServiceStore.get(provider_id)
                agent = AgentMiniService(
                    self.configService,
                    provider,
                    model
                )
                agent._builder(_service.BaseMiniService.QUIET_MINI_SERVICE,build_state,self.CONTAINER_LIFECYCLE_SCOPE)
                counter.count(agent)
                self.MiniServiceStore.add(agent)
            except MiniServiceDoesNotExistsError as e:
                ...
                    
        return super().build(counter, build_state)
    
    async def serve(self):
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
    
    async def stop(self):
        await self.server.stop()