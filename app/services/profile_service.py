from app.definition._service import BaseService, Service
from app.services.config_service import ConfigService
from app.services.security_service import SecurityService
from .database_service import MongooseService, RedisService
from app.models.profile_model import SMTPProfileModel,IMAPProfileModel,TwilioProfileModel

@Service
class ProfileService(BaseService):

    def __init__(self, mongooseService: MongooseService, configService: ConfigService,securityService:SecurityService,redisService:RedisService):
        super().__init__()
        self.mongooseService = mongooseService
        self.configService = configService
        self.securityService = securityService
        self.redisService = redisService
        