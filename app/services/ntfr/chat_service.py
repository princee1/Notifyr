from app.definition._service import Service,BaseService
from app.services.agent.remote_agent_service import RemoteAgentService
from app.services.database.mongoose_service import MongooseService
from app.services.database.redis_service import RedisService

@Service()
class ChatService(BaseService):
    """Answer message with priority because of the rate limite """

    def __init__(self,mongooseService:MongooseService,remoteAgentService:RemoteAgentService,redisService:RedisService) -> None:
        super().__init__()
        self.mongooseService = mongooseService
        self.remoteAgentService = remoteAgentService
        self.redisService = redisService
    
    






