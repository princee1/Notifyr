from ast import Dict
from typing import Type
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, BaseMiniServiceManager, BaseService, MiniService, Service, ServiceStatus
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
    

    def verify_dependency(self):
        if self.vaultService.service_status not in HCVaultService._ping_available_state:
            ...
        
        if self.mongooseService.service_status not in HCVaultService._ping_available_state:
            ...
    
    async def async_verify_dependency(self):
        try:
            async with self.vaultService.statusLock.reader:
                if self.vaultService.service_status not in HCVaultService._ping_available_state:
                    raise ValueError
                
                if not self.vaultService.is_loggedin:
                    raise ValueError
            
            async with self.mongooseService.statusLock.reader:
                if self.mongooseService.service_status not in HCVaultService._ping_available_state:
                    raise ValueError
                    
                if not self.mongooseService.is_connected:
                    raise ValueError
                    
            return True
        except :
            self.service_status = ServiceStatus.TEMPORARY_NOT_AVAILABLE
            return False

    async def add_profile(self,profileType:ProfileModel):
        ...
    
    async def delete_profile(self,profileType:ProfileModel):
        ...
    
    async def get_profile(self,profileType:Type[ProfileModel],profile_id):
        ...
    
    def loadStore(self,):
        ...
    
    def destroyStore(self):
        ...