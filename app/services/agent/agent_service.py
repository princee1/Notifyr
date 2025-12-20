from app.errors.service_error import BuildFailureError
from app.services.config_service import ConfigService
from app.services.database.mongoose_service import MongooseService
from app.services.database.qdrant_service import QdrantService
from app.definition._service import BaseMiniService, MiniService, MiniServiceStore, Service, BaseMiniServiceManager
from .llm_provider_service import LLMProviderService
from .remote_agent_service import RemoteAiAgentService
from app.services import CostService
from grpc import aio
import grpc_tools


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

@Service(is_manager=True)
class AgentService(BaseMiniServiceManager):

    def __init__(self, configService: ConfigService,mongooseService:MongooseService,remoteAgentService:RemoteAiAgentService,llmProviderService:LLMProviderService,costService:CostService,qdrantService:QdrantService) -> None:
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
    