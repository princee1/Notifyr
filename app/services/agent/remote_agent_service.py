import asyncio
from enum import Enum
import functools
from typing import AsyncGenerator, Callable, Generator, Literal, Self
import grpc
import aiohttp
from aiohttp import ClientError, ClientConnectorError, ClientResponseError, ClientTimeout
from json import JSONDecodeError
from app.errors.agentic_error import *
from pydantic import ValidationError
from app.definition import _service
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, BaseMiniServiceManager, BaseService, LinkDep, MiniService, MiniServiceStore, Service, ServiceStatus
from app.errors.service_error import BuildFailureError, BuildOkError, BuildSkipError, BuildWarningError, MiniServiceDoesNotExistsError, ServiceNotAvailableError
from app.errors.agentic_error import AgenticServerDisconnectedError, AgenticStreamDoneError, AgenticBadResponseError, AgenticGrpcIdleError, AgenticGrpcShutdownError
from app.grpc.agent_interceptor import  AgentClientInterceptor,AgentClientAsyncInterceptor
from app.models.odm.agents_model import AgentModel, AgentValidationModel
from app.services.agent.llm_service import LLMMiniService, LLMService
from app.services.config_service import ConfigService
from app.services.cost_service import CostService
from app.services.vault_service import VaultService
from app.services.database.mongoose_service import MongooseService
from app.utils.constant import CostConstant, MongooseDBConstant
from app.utils.globals import APP_MODE, CAPABILITIES,ApplicationMode
from app.grpc import agent_pb2_grpc,agent_message
from app.classes import conversation


acceptable_service_status = {ServiceStatus.AVAILABLE,ServiceStatus.WORKS_ALMOST_ATT,ServiceStatus.PARTIALLY_AVAILABLE}

CREATE_AGENT_BUILD_STATE = -124
AVOID_RE_VALIDATE_BUILD_STATE = -100

PingMode = Literal['http-only','grpc']

_GRPC_RECONNECT_OPTIONS = options = [
    ("grpc.keepalive_time_ms", 10000),       # ping every 10s
    ("grpc.keepalive_timeout_ms", 5000),     # wait 5s
    ("grpc.keepalive_permit_without_calls", 1),
]

_HTTP_HEALTH_CHECK_TIMEOUT = 15  # seconds - timeout per read operation
_HTTP_HEALTH_CHECK_RECONNECT_INTERVAL = 5  # seconds - base interval before reconnect attempt
_HTTP_HEALTH_CHECK_MAX_BACKOFF = 300  # seconds - max backoff (5 minutes)
_HTTP_HEALTH_CHECK_BACKOFF_MULTIPLIER = 2  # exponential backoff factor

class AgenticHTTPState(Enum):
    BAD_RESPONSE = 'Bad Response'
    CONNECTED = 'Connected'
    DISCONNECTED = 'Disconnected'
    STREAM_DONE = 'Stream Done'


@Service(is_manager=True,links=[LinkDep(LLMService,to_build=True,build_state=AVOID_RE_VALIDATE_BUILD_STATE)])
class RemoteAgentService(BaseMiniServiceManager):
    
    def __init__(self,configService:ConfigService,mongooseService:MongooseService,vaultService:VaultService,llmProviderService:LLMService):
        super().__init__()

        self.configService = configService
        self.vaultService = vaultService
        self.llmProviderService = llmProviderService
        self.mongooseService = mongooseService
        self.MiniServiceStore = MiniServiceStore[RemoteAgentMiniService](self.name)
        
        # HTTP health check state
        self.http_state: AgenticHTTPState = AgenticHTTPState.DISCONNECTED
        self.grpc_state: grpc.ChannelConnectivity = grpc.ChannelConnectivity.IDLE

        self.http_health_task: asyncio.Task | None = None
        self._http_session: aiohttp.ClientSession | None = None

    async def pingService(self, infinite_wait:bool, data:dict, profile:str = None, as_manager:bool = False, **kwargs):
        match self.http_state:
            case AgenticHTTPState.DISCONNECTED:
                raise AgenticServerDisconnectedError('Agentic HTTP server is disconnected')
            case AgenticHTTPState.STREAM_DONE:
                raise AgenticStreamDoneError('Agentic HTTP stream ended unexpectedly')
            case AgenticHTTPState.BAD_RESPONSE:
                await asyncio.sleep(0.15)
            case AgenticHTTPState.CONNECTED:
                ...
            case _:
                raise AgenticServerDisconnectedError('Agentic HTTP server state unknown')
    
        if kwargs.get('grpc',False):
            match self.grpc_state:
                case grpc.ChannelConnectivity.READY:
                    ...
                case grpc.ChannelConnectivity.CONNECTING | grpc.ChannelConnectivity.TRANSIENT_FAILURE:
                    await asyncio.sleep(0.2)
                case grpc.ChannelConnectivity.IDLE:
                    raise AgenticGrpcIdleError('Agentic gRPC channel is idle')
                case grpc.ChannelConnectivity.SHUTDOWN:
                    raise AgenticGrpcShutdownError('Agentic gRPC channel is shutdown')
                
        return await super().pingService(infinite_wait, data, profile, as_manager, **kwargs)
    
    def verify_dependency(self):
        if not CAPABILITIES['agentic']:
            raise BuildWarningError('Agentic capability is not enabled')
        
    def build(self, build_state=DEFAULT_BUILD_STATE):
        if APP_MODE == ApplicationMode.agentic:
            raise BuildSkipError("Running in Agentic mode; RemoteAgentService not required.")
                
        if build_state == DEFAULT_BUILD_STATE:
            self.auth_header = self.vaultService.secrets_engine.read('internal-api','AGENTIC')['API_KEY']
        
        models = self.mongooseService.sync_find(MongooseDBConstant.AGENT_COLLECTION,AgentModel)
        counter = self.StatusCounter(len(models))
        self.MiniServiceStore.clear()

        for model in models:
            try:
                provider = self.llmProviderService.MiniServiceStore.get(model['provider'])

                agent = RemoteAgentMiniService(
                    self.configService,
                    self,
                    provider,
                    model
                )
                agent._builder(_service.BaseMiniService.QUIET_MINI_SERVICE,build_state,self.CONTAINER_LIFECYCLE_SCOPE)
                counter.count(agent)
                self.MiniServiceStore.add(agent)
            except MiniServiceDoesNotExistsError as e:
                continue

        return super().build(counter, build_state,True)

    if APP_MODE == ApplicationMode.worker:

        def grpc_state_callback(self,state:grpc.ChannelConnectivity):
            print('State:',state)
            self.grpc_state = state
    
        def connect_channel(self):
            self.channel = grpc.insecure_channel(self.agentic_grpc_host,options=_GRPC_RECONNECT_OPTIONS)
            clientInterceptor = AgentClientInterceptor(self.auth_header)
            self.channel = grpc.intercept_channel(self.channel,clientInterceptor)
            self.stub = agent_pb2_grpc.AgentStub(self.channel)
            try:
                grpc.channel_ready_future(self.channel).result(timeout=5)
                self.channel.subscribe(self.grpc_state_callback,True)

            except grpc.FutureTimeoutError as e:
                self.service_status = ServiceStatus.TEMPORARY_NOT_AVAILABLE
    
    else:

        async def grpc_state_callback(self,state:grpc.ChannelConnectivity):
            print('State:',state)
            async with self.statusLock.writer:
                self.grpc_state = state

        async def connect_channel(self):

            clientInterceptor = AgentClientAsyncInterceptor(self.auth_header)
            self.channel = grpc.aio.insecure_channel(self.agentic_grpc_host,interceptors=[clientInterceptor],options=_GRPC_RECONNECT_OPTIONS)
            self.stub = agent_pb2_grpc.AgentStub(self.channel)
            # try:
            #     grpc.channel_ready_future(self.channel).result(timeout=5)
            #     self.channel.subscribe(self.grpc_state_callback,True)

            # except grpc.FutureTimeoutError as e:
            #     self.service_status = ServiceStatus.TEMPORARY_NOT_AVAILABLE

    async def disconnect_channel(self):
        if self.channel:
            await self.channel.close()
            self.channel = None
            self.stub = None
        
    async def grpc_state_callback(self,state:grpc.ChannelConnectivity):
        print('State:',state)
        async with self.statusLock.writer:
           self.grpc_state = state
                
    def start_agentic_healthcheck(self):
        """Create and start the HTTP health check task."""
        if self.http_health_task and not self.http_health_task.done():
            return 
        
        health_url = f"http://{self.agentic_http_host}/health/"
        headers = {"Authorization": f"Bearer {self.auth_header}"}

        async def _http_health_check():
            http_reconnect_backoff = _HTTP_HEALTH_CHECK_RECONNECT_INTERVAL

            while True:
                try:
                    timeout = aiohttp.ClientTimeout(sock_read=_HTTP_HEALTH_CHECK_TIMEOUT)
                    http_session = aiohttp.ClientSession(timeout=timeout)

                    async with http_session.get(health_url, headers=headers) as response:

                        if response.status != 200:
                            async with self.statusLock.writer:
                                self.http_state = AgenticHTTPState.BAD_RESPONSE
                            
                            await asyncio.sleep(http_reconnect_backoff)
                            continue
                        
                        async with self.statusLock.writer:
                            self.http_state = AgenticHTTPState.CONNECTED

                        http_reconnect_backoff = _HTTP_HEALTH_CHECK_RECONNECT_INTERVAL
                        
                        async for line in response.content:
                            ...

                        async with self.statusLock.writer:
                            self.http_state = AgenticHTTPState.STREAM_DONE

                        await asyncio.sleep(http_reconnect_backoff)
                        continue
                        
                except Exception as e:
                    async with self.statusLock.writer:
                        self.http_state = AgenticHTTPState.DISCONNECTED

                    await http_session.close()
                    await asyncio.sleep(http_reconnect_backoff)
                    http_reconnect_backoff = min(
                        int(http_reconnect_backoff * _HTTP_HEALTH_CHECK_BACKOFF_MULTIPLIER),
                        _HTTP_HEALTH_CHECK_MAX_BACKOFF
                        )
        
        self.http_health_task = asyncio.create_task(_http_health_check())

    async def init_http_session(self, timeout: int = 30):
        """Initialize a shared aiohttp.ClientSession for HTTP requests to agentic."""
        if self._http_session and not self._http_session.closed:
            return

        headers = {"Authorization": f"Bearer {self.auth_header}"}
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        self._http_session = aiohttp.ClientSession(headers=headers, timeout=timeout_obj)

    async def close_http_session(self):
        if self._http_session:
            try:
                await self._http_session.close()
            except Exception:
                pass
            self._http_session = None

    async def request(self, method: str, path: str, *, expected_status=200, **kwargs):
        """Generic HTTP request helper to agentic.

        - method: 'GET'|'POST'|'DELETE' etc.
        - path: must start with '/' or be a full path; will be joined with agentic_http_host
        - expected_status: int or iterable of ints accepted as valid
        Returns parsed JSON body on success.
        Raises Agentic* exceptions on failure.
        """

        if path.startswith('/'):
            url = f"http://{self.agentic_http_host}{path}"
        else:
            url = f"http://{self.agentic_http_host}/{path}"

        method = method.upper()
        # normalize expected_status
        if isinstance(expected_status, int):
            expected = {expected_status}
        else:
            expected = set(expected_status)

        try:
            async with self._http_session.request(method, url, **kwargs) as resp:
                text = await resp.text()
                try:
                    body = await resp.json()
                except JSONDecodeError:
                    body = text
                
                status = resp.status
                if status in expected:
                    return body

                if status == 401 or status == 403:
                    raise AgenticUnauthorizedError(body, status)
                if status == 404:
                    raise AgenticNotFoundError(body, status)
                if 400 <= status < 500:
                    raise AgenticClientError(body, status)
                if 500 <= status < 600:
                    raise AgenticGatewayError(body, status)

                # Fallback
                raise AgenticBadResponseError(f"Unexpected status {status}")

        except asyncio.TimeoutError as e:
            raise AgenticTimeoutError(str(e)) from e
        except ClientConnectorError as e:
            raise AgenticConnectionError(str(e)) from e
        except ClientError as e:
            raise AgenticConnectionError(str(e)) from e
    
    async def cancel_agentic_health_task(self):
        """Cancel the HTTP health check task and cleanup."""
        if self.http_health_task:
            self.http_health_task.cancel()
            try:
                await self.http_health_task
            except asyncio.CancelledError:
                pass
            self.http_health_task = None

        async with self.statusLock.writer:
            self.http_state = False
                 
    @property
    def agentic_grpc_host(self):
        return f"{self.configService.AGENTIC_HOST}:50051"

    @property
    def agentic_http_host(self):
        return f"{self.configService.AGENTIC_HOST}:8000"


@MiniService(links=[LinkDep(LLMMiniService,to_build=True,build_state=AVOID_RE_VALIDATE_BUILD_STATE)])
class RemoteAgentMiniService(BaseMiniService):
    
    def __init__(self,configService:ConfigService,costService:CostService,remoteAgentService:RemoteAgentService,llmProviderMiniService:LLMMiniService,agentModel:dict):
        self.depService = llmProviderMiniService
        super().__init__(llmProviderMiniService, str(agentModel['id']))
        self.configService = configService
        self.remoteAgentService = remoteAgentService
        self.costService = costService
        self.agentModel = agentModel

    def build(self, build_state = ...):
        try: 
            if build_state == DEFAULT_BUILD_STATE:
                m = AgentValidationModel.model_validate(self.agent_model).model_dump()
                self.agent_model:AgentModel = AgentValidationModel.model_construct(**m)
        except ValidationError as e:
            raise BuildFailureError()

    def SilentFail(mode:Literal['direct','generator']):

        def decorator(func:Callable):
            @functools.wraps(func)
            def swrapper(self:Self,request:agent_message.PromptRequest|Callable[...,agent_message.PromptRequest])->agent_message.PromptAnswer:
                if self.service_status not in acceptable_service_status:
                    return
                return func(self,request) 

            @functools.wraps(func)
            async def awrapper(self:Self,request:agent_message.PromptRequest)->agent_message.PromptAnswer:
                if self.service_status not in acceptable_service_status:
                    return
                await self.costService.check_enough_credits(CostConstant.TOKEN_CREDIT,max(self.agent_model.generation.max_tokens or 15600*3,self.depService.model.max_output_tokens or 15600*3))
                return await func(self,request)

            return awrapper if asyncio.iscoroutinefunction(func) else swrapper
        
        return decorator
    
    if APP_MODE == ApplicationMode.worker:

        @SilentFail('direct')
        def Prompt(self, request:agent_message.PromptRequest):
            request = request.to_proto()
            reply = self.remoteAgentService.stub.Prompt(request)
            return agent_message.PromptAnswer.from_proto(reply)

        @SilentFail('direct')
        def Completion(self,):
            ...

    elif APP_MODE == ApplicationMode.server:

        @SilentFail('direct')
        async def Prompt(self, request:agent_message.PromptRequest):
            request = request.to_proto()
            reply = await self.remoteAgentService.stub.Prompt(request)
            return agent_message.PromptAnswer.from_proto(reply)

        @SilentFail('generator')
        async def PromptStream(self, request:agent_message.PromptRequest):
            request = request.to_proto()
            replies = self.remoteAgentService.stub.PromptStream(request)
            async for reply in replies:
                reply = agent_message.PromptAnswer.from_proto(reply)
                yield reply

        @SilentFail('direct')
        async def StreamPrompt(self, request_generator:AsyncGenerator):
            reply = await self.remoteAgentService.stub.StreamPrompt(request_generator)
            return agent_message.PromptAnswer.from_proto(reply)
        
        @SilentFail('generator')
        async def S2SPrompt(self, request_generator:AsyncGenerator):
            replies = self.remoteAgentService.stub.S2SPrompt(request_generator)
            async for reply in replies:
                reply = agent_message.PromptAnswer.from_proto(reply)
                yield reply

        @SilentFail('direct')
        async def Completion(self,request:agent_message.PromptRequest):
            request = request.to_proto()
            reply = await self.remoteAgentService.stub.Completion(request)
            return agent_message.PromptAnswer.from_proto(reply)

        @SilentFail('generator')
        async def S2SBatch(self,request_generator:AsyncGenerator):
            ...