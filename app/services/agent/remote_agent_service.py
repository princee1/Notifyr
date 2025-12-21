import asyncio
import functools
from typing import Callable, Generator, Self

import grpc
from app.definition._service import BaseMiniService, BaseMiniServiceManager, BaseService, MiniService, MiniServiceStore, Service, ServiceStatus
from app.errors.service_error import BuildFailureError, BuildOkError, BuildWarningError, ServiceNotAvailableError
from app.grpc.agent_interceptor import AgentClientAsyncInterceptor,AgentClientInterceptor
from app.services.config_service import ConfigService
from app.services.vault_service import VaultService
from app.services.database.mongoose_service import MongooseService
from app.utils.globals import APP_MODE, CAPABILITIES,ApplicationMode
from grpc import aio
from app.grpc import agent_pb2,agent_pb2_grpc,agent_message


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
        if not CAPABILITIES['agent']:
            raise BuildWarningError
        
        if APP_MODE == ApplicationMode.agentic:
            raise BuildOkError
        
    def build(self, build_state=...):
        auth_header = self.vaultService.secrets_engine.read('internal-api','AGENTIC')
        print(auth_header)

    def register_channel(self):
        if self.service_status != ServiceStatus.AVAILABLE:
            raise ServiceNotAvailableError
        
        clientInterceptor = AgentClientAsyncInterceptor('ok') if APP_MODE == ApplicationMode.server else AgentClientInterceptor
        channel = grpc.insecure_channel(self.configService.AGENTIC_HOST)
        grpc.intercept_channel(channel,clientInterceptor)
        self.stub = agent_pb2_grpc.AgentStub(channel)

@MiniService()
class RemoteAgentMiniService(BaseMiniService):
    
    def __init__(self,configService:ConfigService,remoteAgentService:RemoteAgentService):
        super().__init__(None, id)
        self.configService = configService
        self.remoteAgentService = remoteAgentService

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
            reply = agent_message.PromptAnswer.from_proto(reply)

    elif APP_MODE == ApplicationMode.server:

        @SilentFail
        async def Prompt(self, request:agent_message.PromptRequest):
            request = request.to_proto()
            reply = self.remoteAgentService.stub.Prompt(request)
            reply = agent_message.PromptAnswer.from_proto(reply)

        @SilentFail
        async def PromptStream(self, request:agent_message.PromptRequest)->None:
            request = request.to_proto()
            replies = self.remoteAgentService.stub.PromptStream(request)
            for reply in replies:
                reply = agent_message.PromptAnswer.from_proto(reply)

        @SilentFail
        async def StreamPrompt(self, callback:Callable[[],agent_message.PromptRequest]):
            request_generator=iterator_factory(callback=callback)
            reply = self.remoteAgentService.stub.StreamPrompt(request_generator())
            reply = agent_message.PromptAnswer.from_proto(reply)
        
        @SilentFail
        async def S2SPrompt(self, callback:Callable[[],agent_message.PromptRequest]):
            request_generator=iterator_factory(callback=callback)
            replies = self.remoteAgentService.stub.S2SPrompt(request_generator)
            for reply in replies:
                reply = agent_message.PromptAnswer.from_proto(reply)
        
