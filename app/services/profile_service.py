from ast import Dict
from random import randint
from typing import Type
from app.classes.secrets import SecretsWrapper
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, BaseMiniServiceManager, BaseService, MiniService, Service, ServiceStatus
from app.services.config_service import ConfigService
from app.services.logger_service import LoggerService
from app.services.secret_service import HCVaultService
from app.utils.constant import VaultConstant
from .database_service import MongooseService, RedisService
from app.models.profile_model import ProfileModel, SMTPProfileModel,IMAPProfileModel,TwilioProfileModel

@MiniService
class ProfileMiniService(BaseMiniService):
    ...
    # TODO each profiles has a services

@Service
class ProfileService(BaseMiniServiceManager):

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


    async def add_profile(self,profile:ProfileModel):
        creds = {}

        for skey in profile.secrets_keys:
            secret = getattr(profile,skey,None)
            if isinstance(secret,str):
                setattr(profile,skey,randint(40,60)*'*')
            elif isinstance(secret,(int,float)):
                setattr(profile,skey,randint(1000000,10000000))
            elif isinstance(secret,dict):
                setattr(profile,skey,{})
            else:
                setattr(profile,skey,None)
            
            if secret != None:
                if isinstance(secret,dict):
                    creds.update(secret)
                else:
                    creds[skey] = secret
            
        
        result:ProfileModel = await self.mongooseService.save(profile)
        result_id = str(result.id)
        self._put_encrypted_creds(result_id,creds)
        return result
    
    async def delete_profile(self,profileModel:ProfileModel):
        profile_id = str(profileModel.id)
        await profileModel.delete()
        self._delete_encrypted_creds(profile_id)

    async def update_profile(self,profileModel:ProfileModel,body:dict):
        ...


    def _read_encrypted_creds(self,profiles_id:str):
        data = self.vaultService.secrets_engine.read(VaultConstant.PROFILES_SECRETS,profiles_id)
        for k,v in data.items():
            data[k]= self.vaultService.transit_engine.decrypt(v,VaultConstant.PROFILES_KEY)
        
        data = SecretsWrapper(data)
        return data

    def _put_encrypted_creds(self,profiles_id:str,data:dict):
        for k,v in data.items():
            data[k] = self.vaultService.transit_engine.encrypt(v,VaultConstant.PROFILES_KEY)
        
        return self.vaultService.secrets_engine.put(VaultConstant.PROFILES_SECRETS,data,profiles_id)

    def _delete_encrypted_creds(self,profiles_id:str):
        return self.vaultService.secrets_engine.delete(VaultConstant.NOTIFYR_SECRETS_MOUNT_POINT,profiles_id)


    def loadStore(self,):
        ...
    
    def destroyStore(self):
        ...