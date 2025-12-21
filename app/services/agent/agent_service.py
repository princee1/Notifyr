import asyncio
from app.errors.service_error import BuildFailureError
from app.services.config_service import ConfigService
from app.services.database.mongoose_service import MongooseService
from app.services.database.qdrant_service import QdrantService
from app.definition._service import BaseMiniService, LinkDep, MiniService, MiniServiceStore, Service, BaseMiniServiceManager
from .llm_provider_service import LLMProviderService
from .remote_agent_service import RemoteAgentService
from app.services import CostService
from grpc import aio
from concurrent import futures
import grpc

from app.grpc import agent_pb2_grpc,agent_pb2,agent_message



@MiniService()
class AiAgentMiniService(BaseMiniService):
    ...
    """
    will register the tools
    and store the agent config
    call the provider
    tools idea:
        - research on the internet
        - knowledge graph
        - rag
        - rest,graphql, rpc fetch api
    """

@Service(is_manager=True,
         links=[LinkDep(RemoteAgentService)]
         )
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
        
    def __init__(self, configService: ConfigService,mongooseService:MongooseService,remoteAgentService:RemoteAgentService,llmProviderService:LLMProviderService,costService:CostService,qdrantService:QdrantService) -> None:
        super().__init__()
        self.configService = configService
        self.mongooseService = mongooseService
        self.llmProviderService = llmProviderService
        self.remoteAgentService = remoteAgentService
        self.costService = costService
        self.qdrantService = qdrantService

        self.MiniServiceStore = MiniServiceStore[AiAgentMiniService](self.name)

    def verify_dependency(self):
        if not self.configService.getenv('AI_ENABLED',False):
            raise BuildFailureError

    def build(self, build_state=...):
        self._api_keys = {}
        counter = self.StatusCounter(0)
        return
        return super().build(counter, build_state)
    
    async def serve(self):
        self.server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
        agent_pb2_grpc.add_AgentServicer_to_server(self,self.server)
        self.server.add_insecure_port('agentic:50051')
        await self.server.start()
        await self.server.wait_for_termination()
    
    async def stop(self):
        await self.server.stop()