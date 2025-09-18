from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, BaseService, MiniService, Service
from app.services.config_service import ConfigService
from app.services.logger_service import LoggerService
from app.services.secret_service import HCVaultService
from .database_service import MongooseService, RedisService
from app.models.profile_model import SMTPProfileModel,IMAPProfileModel,TwilioProfileModel

@Service
class ProfileManagerService(BaseService):

    def __init__(self, mongooseService: MongooseService, configService: ConfigService,redisService:RedisService,loggerService:LoggerService,vaultService:HCVaultService):
        super().__init__()
        self.mongooseService = mongooseService
        self.configService = configService
        self.redisService = redisService
        self.loggerService = loggerService
        self.vaultService = vaultService
    
    def build(self, build_state = DEFAULT_BUILD_STATE):
        ...
    


@MiniService
class ProfileMiniService(BaseMiniService):
    ...

    # TODO each profiles has a services