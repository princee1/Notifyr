from ast import Dict
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, BaseMiniServiceManager, BaseService, MiniService, Service
from app.services.config_service import ConfigService
from app.services.logger_service import LoggerService
from app.services.secret_service import HCVaultService
from .database_service import MongooseService, RedisService
from app.models.profile_model import ProfileModel, SMTPProfileModel,IMAPProfileModel,TwilioProfileModel

@MiniService
class ProfileMiniService(BaseMiniService):
    ...
    # TODO each profiles has a services

@Service
class ProfileManagerService(BaseMiniServiceManager):

    def __init__(self, mongooseService: MongooseService, configService: ConfigService,redisService:RedisService,loggerService:LoggerService,vaultService:HCVaultService):
        super().__init__()
        self.mongooseService = mongooseService
        self.configService = configService
        self.redisService = redisService
        self.loggerService = loggerService
        self.vaultService = vaultService
    
    def build(self, build_state = DEFAULT_BUILD_STATE):
        ...
    

    async def add_profile(self,profileType:ProfileModel):
        ...
    
    async def delete_profile(self,profileType:ProfileModel):
        ...
    
    async def get_profile(self,profileType:ProfileModel):
        ...
    
    def loadStore(self,):
        ...
    
    def destroyStore(self):
        ...