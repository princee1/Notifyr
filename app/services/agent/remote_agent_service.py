import asyncio
import functools
from typing import Callable, Generator, Self
import grpc
from app.definition import _service
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, BaseMiniServiceManager, BaseService, MiniService, MiniServiceStore, Service, ServiceStatus
from app.errors.service_error import BuildFailureError, BuildOkError, BuildWarningError, ServiceNotAvailableError
from app.grpc.agent_interceptor import  AgentClientInterceptor,AgentClientAsyncInterceptor
from app.models.agents_model import AgentModel
from app.services.config_service import ConfigService
from app.services.vault_service import VaultService
from app.services.database.mongoose_service import MongooseService
from app.utils.constant import MongooseDBConstant
from app.utils.globals import APP_MODE, CAPABILITIES,ApplicationMode
from app.grpc import agent_pb2_grpc,agent_message


CREATE_AGENT_BUILD_STATE = -124

def iterator_factory(callback,wait=0.5):
    async def request_generator():
        while True:
            request: agent_message.PromptRequest = await callback()
            if request == None:
                break
            request = request.to_proto()
            yield request
            asyncio.sleep(wait)

    return request_generator

@Service(is_manager=True)
class RemoteAgentService(BaseMiniServiceManager):
    
    def __init__(self,configService:ConfigService,mongooseService:MongooseService,vaultService:VaultService):
        super().__init__()

        self.configService = configService
        self.vaultService = vaultService
        self.mongooseService = mongooseService
        self.MiniServiceStore = MiniServiceStore[RemoteAgentMiniService](self.name)
    
    def verify_dependency(self):
        if not CAPABILITIES['agentic']:
            raise BuildWarningError('Agentic capability is not enabled')
        
    def build(self, build_state=DEFAULT_BUILD_STATE):
        if APP_MODE == ApplicationMode.agentic:
            raise BuildOkError("Running in Agentic mode; RemoteAgentService not required.")
        
        if build_state == DEFAULT_BUILD_STATE:
            self.auth_header = self.vaultService.secrets_engine.read('internal-api','AGENTIC')['API_KEY']
        
        models = self.mongooseService.sync_find(MongooseDBConstant.AGENT_COLLECTION,AgentModel)
        counter = self.StatusCounter(len(models))
        self.MiniServiceStore.clear()

        for model in models:
            agent = RemoteAgentMiniService(
                self.configService,
                self,
                model
            )
            agent._builder(_service.BaseMiniService.QUIET_MINI_SERVICE,build_state,self.CONTAINER_LIFECYCLE_SCOPE)
            counter.count(agent)
            self.MiniServiceStore.add(agent)
        
        return super().build(counter, build_state)


    def register_channel(self):
        
        if APP_MODE == ApplicationMode.worker:
            self.channel = grpc.insecure_channel(self.agentic_grpc_host)
            clientInterceptor = AgentClientInterceptor(self.auth_header)
            self.channel = grpc.intercept_channel(self.channel,clientInterceptor)
        else:
            clientInterceptor = AgentClientAsyncInterceptor(self.auth_header)
            self.channel = grpc.aio.insecure_channel(self.agentic_grpc_host,interceptors=[clientInterceptor])

        self.stub = agent_pb2_grpc.AgentStub(self.channel)
    
    async def disconnect_channel(self):
        if self.service_status != ServiceStatus.AVAILABLE:
            raise ServiceNotAvailableError
        if self.channel:
            await self.channel.close()
            self.channel = None
            self.stub = None

    @property
    def agentic_grpc_host(self):
        return f"{self.configService.AGENTIC_HOST}:50051"

    @property
    def agentic_http_host(self):
        return f"{self.configService.AGENTIC_HOST}:8000"


@MiniService()
class RemoteAgentMiniService(BaseMiniService):
    
    def __init__(self,configService:ConfigService,remoteAgentService:RemoteAgentService,agentModel:AgentModel):

        super().__init__(None, str(agentModel.id))
        self.configService = configService
        self.remoteAgentService = remoteAgentService
        self.agentModel = agentModel

    def SilentFail(func:Callable):
        @functools.wraps(func)
        def swrapper(self:Self,request:agent_message.PromptRequest|Callable[...,agent_message.PromptRequest]):
            if self.service_status != ServiceStatus.AVAILABLE:
                return
            return func(self,request) 

        @functools.wraps(func)
        async def awrapper(self:Self,request:agent_message.PromptRequest):
            if self.service_status != ServiceStatus.AVAILABLE:
                return
            return await func(self,request)

        return awrapper if asyncio.iscoroutinefunction(func) else swrapper
    
    if APP_MODE == ApplicationMode.worker:

        @SilentFail
        def Prompt(self, request:agent_message.PromptRequest):
            request = request.to_proto()
            reply = self.remoteAgentService.stub.Prompt(request)
            return agent_message.PromptAnswer.from_proto(reply)

    elif APP_MODE == ApplicationMode.server:

        @SilentFail
        async def Prompt(self, request:agent_message.PromptRequest):
            request = request.to_proto()
            reply = self.remoteAgentService.stub.Prompt(request)
            return agent_message.PromptAnswer.from_proto(reply)

        @SilentFail
        async def PromptStream(self, request:agent_message.PromptRequest)->None:
            request = request.to_proto()
            replies = self.remoteAgentService.stub.PromptStream(request)
            for reply in replies:
                reply = agent_message.PromptAnswer.from_proto(reply)

        @SilentFail
        async def StreamPrompt(self, callback:Callable[[],agent_message.PromptRequest]):
            request_generator=iterator_factory(callback=callback)
            reply = self.remoteAgentService.stub.StreamPrompt(request_generator)
            return agent_message.PromptAnswer.from_proto(reply)
        
        @SilentFail
        async def S2SPrompt(self, callback:Callable[[],agent_message.PromptRequest]):
            request_generator=iterator_factory(callback=callback)
            replies = self.remoteAgentService.stub.S2SPrompt(request_generator)
            for reply in replies:
                reply = agent_message.PromptAnswer.from_proto(reply)
        
