from app.definition._service import Service,BaseService
from app.services.agent.remote_agent_service import RemoteAgentService
from app.services.config_service import ConfigService
from app.services.database.mongoose_service import MongooseService
from app.services.database.redis_service import RedisService

@Service()
class ChatService(BaseService):
    """Answer message with priority because of the rate limit """

    def __init__(self,configService:ConfigService,mongooseService:MongooseService,remoteAgentService:RemoteAgentService,redisService:RedisService) -> None:
        super().__init__()
        self.mongooseService = mongooseService
        self.remoteAgentService = remoteAgentService
        self.redisService = redisService
        self.configService = configService
    
    def start_chat(self):
        ...
    
    def end_chat(self):
        ...
    
    async def answer(self,message:str,agent:str|None,thread:str):
        """Answer message with priority because of the rate limit """
        async with self.remoteAgentService.statusLock.reader:
            remoteAgent = self.remoteAgentService.MiniServiceStore.get(agent)
            async with remoteAgent.statusLock.reader:
                reply = await remoteAgent.Prompt()

    async def answer_stream(self,message:str,agent:str|None,thread:str):
        """Answer message with priority because of the rate limit """
        async with self.remoteAgentService.statusLock.reader:
            remoteAgent = self.remoteAgentService.MiniServiceStore.get(agent)
            async with remoteAgent.statusLock.reader:
                reply = await remoteAgent.PromptStream()

    async def fetch_chat(self,):
        ...
