from datetime import datetime
from random import randint
from typing import Literal, Type

from pydantic import ValidationError
from app.classes.secrets import ChaCha20Poly1305SecretsWrapper, ChaCha20SecretsWrapper
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, BaseMiniServiceManager, BaseService, MiniService, MiniServiceStore, Service, ServiceStatus
from app.errors.db_error import MongoCollectionDoesNotExists
from app.errors.service_error import BuildFailureError, BuildOkError
from app.services.config_service import ConfigService
from app.services.database.mongoose_service import MongooseService
from app.services.database.redis_service import RedisService
from app.services.logger_service import LoggerService
from app.services.vault_service import VaultService
from app.utils.constant import MongooseDBConstant, VaultConstant
from app.utils.helper import flatten_dict, subset_model
from app.models.communication_model import  BaseProfileModel, ProfilModelValues
from app.classes.profiles import ErrorProfileModel
from typing import Generic, TypeVar
from app.utils.tools import RunInThreadPool

TModel = TypeVar("TModel",bound=BaseProfileModel)

@MiniService(
    override_init=True
)
class ProfileMiniService(BaseMiniService,Generic[TModel]):
    
    def __init__(self,vaultService:VaultService,mongooseService:MongooseService,redisService:RedisService, model:TModel,model_type:Type[TModel]=None):
        if model_type != None:
            self.model_type = model_type
            self.validationModel = subset_model(self.model_type,f'Validation{self.model_type.__class__.__name__}')
            super().__init__(None,str(model['_id']))
            self.queue_name = f'{self.model_type._queue}:{self.miniService_id}'

        else:
            super().__init__(None,str(model.id))
            self.queue_name = f'{model._queue}:{self.miniService_id}'

        self.model:TModel = model
        self.credentials:ChaCha20Poly1305SecretsWrapper = ...
        self.vaultService = vaultService
        self.mongooseService = mongooseService
        self.redisService = redisService
        
    def build(self, build_state = ...):
        try:
            if self.model_type != None:
                m = self.validationModel.model_validate(self.model).model_dump()
                self.model = self.model_type.model_construct(**m)
        except ValidationError as e:
            raise BuildFailureError()
        
        self._read_encrypted_creds()
        
    def _read_encrypted_creds(self,return_only=False):
        data = self.vaultService.secrets_engine.read(self.model._vault,self.miniService_id)
        for k,v in data.items():
            data[k]= self.vaultService.transit_engine.decrypt(v,VaultConstant.PROFILES_KEY)
        
        if return_only:
            return data
        else:
            self.credentials = ChaCha20Poly1305SecretsWrapper(data)
            return 

    async def async_create_profile(self):
        print('Template Profile Model:', TModel)
        self.model = await self.mongooseService.get(self.model.__class__,self.miniService_id)
        await RunInThreadPool(self._read_encrypted_creds)()
        


@Service(is_manager=True)
class ProfileService(BaseMiniServiceManager):

    def __init__(self, mongooseService: MongooseService, configService: ConfigService,redisService:RedisService,loggerService:LoggerService,vaultService:VaultService):
        super().__init__()
        self.MiniServiceStore:MiniServiceStore[ProfileMiniService[BaseProfileModel]] = MiniServiceStore[ProfileMiniService[BaseProfileModel]](self.__class__.__name__)
        self.mongooseService = mongooseService
        self.configService = configService
        self.redisService = redisService
        self.loggerService = loggerService
        self.vaultService = vaultService
    
    def build(self, build_state = DEFAULT_BUILD_STATE):
        self.MiniServiceStore.clear()
        
        for v in ProfilModelValues.values():
            for m in self.mongooseService.sync_find(v._collection,v):
                p = ProfileMiniService[v](
                    self.vaultService,
                    self.mongooseService,
                    self.redisService,
                    model=m,model_type=v)
                p._builder(BaseMiniService.QUIET_MINI_SERVICE,build_state,self.CONTAINER_LIFECYCLE_SCOPE)
                self.MiniServiceStore.add(p)
        
        if len(self.MiniServiceStore) == 0:
            raise BuildOkError
             
    def verify_dependency(self):
        if self.vaultService.service_status not in VaultService._ping_available_state:
            raise BuildFailureError
        
        if self.mongooseService.service_status not in VaultService._ping_available_state:
            raise BuildFailureError
    
    async def async_verify_dependency(self):
        try:
            async with self.vaultService.statusLock.reader:
                if self.vaultService.service_status not in VaultService._ping_available_state:
                    raise ValueError
                
                if not self.vaultService.is_loggedin:
                    raise ValueError
            
            async with self.mongooseService.statusLock.reader:
                if self.mongooseService.service_status not in VaultService._ping_available_state:
                    raise ValueError
                    
                if not self.mongooseService.is_connected:
                    raise ValueError
                    
            return True
        except :
            self.service_status = ServiceStatus.TEMPORARY_NOT_AVAILABLE
            return False
    
    ########################################################       ################################3

    async def add_profile(self,profile:BaseProfileModel):
        creds = {}

        for skey in profile._secrets_keys:
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
                if not isinstance(secret,(dict,str,int,float,bool)):
                    raise TypeError
                
                creds[skey] = secret
            
        result:BaseProfileModel = await self.mongooseService.insert(profile)
        result_id = str(result.id)
        await self._put_encrypted_creds(result_id,creds,result._vault)
        return result
    
    async def delete_profile(self,profileModel:BaseProfileModel,raise_:bool = False):
        profile_id = str(profileModel.id)
        result = await profileModel.delete()
        await self._delete_encrypted_creds(profile_id,profileModel._vault)
        return result
     
    async def update_profile(self,profileModel:BaseProfileModel,modelUpdate:BaseProfileModel):
        modelUpdate = modelUpdate.model_dump()
        for k,v in modelUpdate.items():
            if v is not None:
                try:
                    getattr(profileModel,k)
                    setattr(profileModel,k,v)
                except:
                    continue
   
    async def update_meta_profile(self,profile:BaseProfileModel):
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

    async def update_credentials(self,profiles_id:str,creds:dict,vault_path:str):
        current_creds:dict = await self._read_encrypted_creds(profiles_id)
        current_creds.update(creds)
        await self._put_encrypted_creds(profiles_id,current_creds,vault_path)

    @RunInThreadPool
    def _read_encrypted_creds(self,profile_id:str):
        return self.MiniServiceStore.get(profile_id)._read_encrypted_creds(True)    

    @RunInThreadPool
    def _put_encrypted_creds(self,profiles_id:str,data:dict,vault_path:str):
        data = flatten_dict(data,dict_sep='/',_key_builder=lambda x:x+'/')
        for k,v in data.items():
            if not isinstance(v,str):
                v = str(v)
            
            data[k] = self.vaultService.transit_engine.encrypt(v,VaultConstant.PROFILES_KEY)
        
        return self.vaultService.secrets_engine.put(vault_path,data,profiles_id)

    @RunInThreadPool
    def _delete_encrypted_creds(self,profiles_id:str,vault_path):
        return self.vaultService.secrets_engine.delete(vault_path,profiles_id)
    
    ########################################################       ################################
