from app.services.config_service import ConfigService
from app.services.database.mongoose_service import MongooseService
from app.services.profile_service import ProfileService
from app.definition._service import BaseMiniService, MiniService, MiniServiceStore, Service, BaseMiniServiceManager
from .llm_provider_service import LLMProviderService
from .remote_agent_service import RemoteAgenticMiniService,RemoteAiAgentService


@MiniService()
class AiAgentMiniService(BaseMiniService):
    ...
    """
    will register the tools
    and store the agent config
    call the provider
    tools idea:
        - research on the internet
        - reflect
        - rag

    """

@Service()
class AgentService(BaseMiniServiceManager):

    def __init__(self, configService: ConfigService,mongooseService:MongooseService,profileService:ProfileService,remoteAgentService:RemoteAiAgentService,llmProviderService:LLMProviderService) -> None:
        super().__init__()
        self.configService = configService
        self.mongooseService = mongooseService
        self.llmProviderService = llmProviderService
        self.remoteAgentService = remoteAgentService
        self.profileService= profileService
        self.MiniServiceStore = MiniServiceStore[AiAgentMiniService](self.name)

    def verify_dependency(self):
        ...

    def build(self, build_state=...):
        self._api_keys = {}
        counter = self.StatusCounter(0)
        return super().build(counter, build_state)
    