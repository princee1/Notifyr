from app.definition._service import DEFAULT_BUILD_STATE, BaseService, Service
from app.services.chat_service import ChatService
from app.services.config_service import ConfigService
from app.services.database.mongoose_service import MongooseService
from app.services.database.redis_service import RedisService
from app.services.setting_service import SettingService

@Service()
class LiveChatService(BaseService):
    
    def __init__(self,configService:ConfigService,redisService:RedisService,mongooseService:MongooseService,chatService:ChatService,settingService:SettingService):
        super().__init__()
        self.configService = configService
        self.redisService = redisService
        self.mongooseService = mongooseService
        self.chatService = chatService
        self.settingService = settingService
    
    def build(self, build_state = DEFAULT_BUILD_STATE):
        ...


    def create_live_chat_session(self):
        ...