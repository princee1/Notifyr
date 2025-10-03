from datetime import datetime
from random import randint
from typing import Literal, Type
from app.classes.secrets import SecretsWrapper
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, BaseMiniServiceManager, BaseService, MiniService, MiniServiceStore, Service, ServiceStatus
from app.errors.db_error import MongoCollectionDoesNotExists
from app.errors.service_error import BuildFailureError
from app.services.config_service import ConfigService
from app.services.logger_service import LoggerService
from app.services.secret_service import HCVaultService
from app.utils.constant import MongooseDBConstant, VaultConstant
from .database_service import MongooseService, RedisService
from app.models.profile_model import ErrorProfileModel, ProfileModel, SMTPProfileModel,IMAPProfileModel,TwilioProfileModel, ProfilModelValues
from typing import Generic, TypeVar

TModel = TypeVar("TModel",bound=ProfileModel)

@MiniService(
    override_init=True
)
class ProfileMiniService(BaseMiniService,Generic[TModel]):
    
    def __init__(self,vaultService:HCVaultService,mongooseService:MongooseService,redisService:RedisService, model:TModel):
        super().__init__(None,str(model.id))
        self.model:TModel = model
        self.credentials = ...
        self.vaultService = vaultService
        self.mongooseService = mongooseService
        self.redisService = redisService
    
    def build(self, build_state = ...):
        self._read_encrypted_creds()
                
    def _read_encrypted_creds(self):
        data = self.vaultService.secrets_engine.read(VaultConstant.PROFILES_SECRETS,self.miniService_id)
        for k,v in data.items():
            data[k]= self.vaultService.transit_engine.decrypt(v,VaultConstant.PROFILES_KEY)
        self.credentials =  SecretsWrapper(data)
    
    async def async_build(self):
        print('Template Profile Model:', TModel)
        self.model = await self.mongooseService.get(self.model.__class__,self.miniService_id)
        self._read_encrypted_creds()
        


@Service()
class ProfileService(BaseMiniServiceManager):

    def __init__(self, mongooseService: MongooseService, configService: ConfigService,redisService:RedisService,loggerService:LoggerService,vaultService:HCVaultService):
        super().__init__()
        self.MiniServiceStore:MiniServiceStore[ProfileMiniService[ProfileModel]] = MiniServiceStore[ProfileMiniService[ProfileModel]]()
        self.mongooseService = mongooseService
        self.configService = configService
        self.redisService = redisService
        self.loggerService = loggerService
        self.vaultService = vaultService
    
    def build(self, build_state = DEFAULT_BUILD_STATE):
        try:
            for v in ProfilModelValues.values():
                for m in self.mongooseService.sync_find(MongooseDBConstant.PROFILE_COLLECTION,v):
                    p = ProfileMiniService[v](
                        self.vaultService,
                        self.mongooseService,
                        self.redisService,
                        model=m)
                    p._builder(BaseMiniService.QUIET_MINI_SERVICE,build_state,self.CONTAINER_LIFECYCLE_SCOPE)
                    self.MiniServiceStore.add(p)
        except MongoCollectionDoesNotExists:
            raise BuildFailureError

    
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

    ########################################################       ################################3

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
            
        
        result:ProfileModel = await self.mongooseService.insert(profile)
        result_id = str(result.id)
        self._put_encrypted_creds(result_id,creds)
        return result
    
    async def delete_profile(self,profileModel:ProfileModel,raise_:bool = False):
        profile_id = str(profileModel.id)
        result = await profileModel.delete()
        self._delete_encrypted_creds(profile_id)
     
    async def update_profile(self,profileModel:ProfileModel,body:dict):
        for k,v in body.items():
            if v is not None:
                try:
                    getattr(profileModel,k)
                    setattr(profileModel,k,v)
                except:
                    continue
        
    def update_credentials(self,profiles_id:str,creds:dict):
        current_creds = self._read_encrypted_creds(profiles_id,False)
        current_creds.update(creds)
        self._put_encrypted_creds(profiles_id,current_creds)

    async def update_meta_profile(self,profile:ProfileModel):
        profile.last_modified =  datetime.utcnow().isoformat()
        profile.version+=1
        await profile.save()
        return profile

    ########################################################       ################################

    async def addError(self,profile_id: str | None,error_code: int | None,error_name: str | None,error_description: str | None,error_type: Literal['warn', 'critical', 'message'] | None):
        error= ErrorProfileModel(
            profile_id=profile_id,
            error_code=error_code,
            error_name=error_name,
            error_description=error_description,
            error_type=error_type)
        error = ErrorProfileModel.model_validate(error)
        await self.mongooseService.insert(error)
    
    async def deleteError(self,profile_id:str):
        await self.mongooseService.delete_all(ErrorProfileModel,{'profile_id':profile_id})
    ########################################################       ################################

    def _put_encrypted_creds(self,profiles_id:str,data:dict):
        for k,v in data.items():
            data[k] = self.vaultService.transit_engine.encrypt(v,VaultConstant.PROFILES_KEY)
        
        return self.vaultService.secrets_engine.put(VaultConstant.PROFILES_SECRETS,data,profiles_id)

    def _delete_encrypted_creds(self,profiles_id:str):
        return self.vaultService.secrets_engine.delete(VaultConstant.PROFILES_SECRETS,profiles_id)
    
    ########################################################       ################################

    def loadStore(self,):
        ...
    
    def destroyStore(self):
        ...