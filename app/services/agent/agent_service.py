import asyncio
from fastapi import HTTPException
from app.errors.service_error import BuildFailureError
from app.grpc.agent_interceptor import AgentServerInterceptor, HandlerType
from app.services.config_service import ConfigService
from app.services.database.mongoose_service import MongooseService
from app.services.database.qdrant_service import QdrantService
from app.definition._service import BaseMiniService, LinkDep, MiniService, MiniServiceStore, Service, BaseMiniServiceManager
from app.services.profile_service import ProfileService
from app.services.database.neo4j_service import Neo4JService
from app.services.reactive_service import ReactiveService
from app.services.vault_service import VaultService
from .llm_provider_service import LLMProviderService
from .remote_agent_service import RemoteAgentService
from concurrent import futures
import grpc
from app.grpc import agent_pb2_grpc,agent_pb2,agent_message


@MiniService()
class AgentMiniService(BaseMiniService):
    ...
    """
    will register the tools
    and store the agent config
    graph of tools
    call the provider
    tools idea:
        - research on the internet,crawl web 
        - knowledge graph
        - qdrant rag
        - rest,graphql, fetch api
        - connect to a mcp
    """



@Service(is_manager=True,links=[LinkDep(RemoteAgentService)])
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

    def build(self, build_state=...):
        counter = self.StatusCounter(0)
        secrets = self.vaultService.secrets_engine.read('internal-api','AGENTIC')
        if 'API_KEY' not in secrets:
            raise BuildFailureError()
        self.auth_header = secrets['API_KEY']
        return
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