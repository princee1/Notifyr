
import asyncio
from random import randint, random
import time
from typing import Dict, Union
import hvac
from typing_extensions import Literal
from app.classes.vault_engine import VaultDatabaseCredentials
from app.definition._service import AbstractServiceClass, BaseService, ServiceStatus
from app.errors.db_error import VaultCredentialAlreadyExistError, VaultCredentialNameDoesNotExistError
from app.errors.service_error import BuildFailureError, ServiceTemporaryNotAvailableError
from app.interface.timers import IntervalParams, SchedulerInterface
from app.services.config_service import ConfigService
from app.services.file.file_service import FileService
from app.services.vault_service import VaultService
from app.utils.constant import VaultConstant
from app.utils.globals import APP_MODE
from app.utils.toolbox import RunInThreadPool

CREDS_NAME_KEY='__cred_name__'
CredentialName = Union[Literal['default'],str]
MultiCredentialsStore = Dict[Literal['default']|str,VaultDatabaseCredentials]



@AbstractServiceClass()
class DatabaseService(BaseService): 
    def __init__(self,configService:ConfigService,fileService:FileService) -> None:
        BaseService.__init__(self)
        self.configService= configService
        self.fileService = fileService

@AbstractServiceClass()
class TempCredentialsDatabaseService(DatabaseService,SchedulerInterface):

    def __init__(self,configService:ConfigService,fileService:FileService,vaultService:VaultService,ttl,max_retry=2,wait_time=2,t:Literal['constant','linear']='constant',b=0):
        DatabaseService.__init__(self,configService,fileService)
        SchedulerInterface.__init__(self,replace_existing=True,thread_pool_count=1)
        self.vaultService = vaultService
        self.creds:MultiCredentialsStore = {}
        self.max_retry = max_retry
        self.wait_time = wait_time
        self.t=t
        self.b = b
        self.last_rotated = None
        self.auth_ttl = ttl
        self.interval_built = False

    def build(self, build_state = ...):
        if not self.interval_built:
            delay = IntervalParams( seconds=self.random_buffer_interval(self.auth_ttl) )
            self.interval_schedule(delay, self.creds_rotation,tuple(),{},f"{self.name}-[{APP_MODE}]-creds_rotation")
            self.interval_built = True
        

    def add_credentials(self,role:VaultConstant.NotifyrDynamicSecretsRole,name:CredentialName='default',prefix:str=None,suffix:str=None,strict=False):
        if name in self.creds:
            self.revoke_lease(name)
            if strict:
                raise VaultCredentialAlreadyExistError(name)

        cred = self.vaultService.database_engine.generate_credentials(role,prefix,suffix)
        self.creds[name] = cred
        
    def get_credentials(self,name:CredentialName):
        if name not in self.creds:
            raise VaultCredentialNameDoesNotExistError(name)

        return self.creds[name]

    def verify_dependency(self):
        if self.vaultService.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError("Vault Service can’t issue creds")

    async def pingService(self,infinite_wait:bool,data:dict,profile:str=None,as_manager:bool=False,**kwargs):
        cred_name:CredentialName = kwargs.get(CREDS_NAME_KEY,'default')
        self.check_auth()
        await super().pingService(infinite_wait,data,profile,as_manager,**kwargs)
             
    @staticmethod
    def random_buffer_interval(ttl):
        return ttl - (ttl*.08*random() + randint(20,40))

    def renew_db_creds(self,name:CredentialName='default'):
        lease_id = self.lease_id(name)
        if not lease_id:
            return
        self.vaultService.renew_lease(lease_id,3600)
    
    def db_user(self,name:CredentialName='default'):
        creds = self.get_credentials(name)
        return creds.get('data',dict()).get('username',None)
        
    def db_password(self,name:CredentialName='default'):
        creds = self.get_credentials(name)
        return creds.get('data',dict()).get('password',None)

    def lease_id(self,name:CredentialName='default'):
        creds = self.get_credentials(name)
        return creds.get('lease_id',None)
    
    def revoke_lease(self,name:CredentialName='default'):
        try:
            return self.vaultService.revoke_lease(self.lease_id(name))
        except Exception as e:
            print(e)

    async def _check_vault_status(self):
        async with self.vaultService.lock('reader'):
            return self.vaultService.service_status

    async def creds_rotation(self):
        temp_service = await self._check_vault_status()
        async with self.lock('writer'):
            retry =0
            while retry<self.max_retry:
                try:
                    if temp_service == ServiceStatus.AVAILABLE:
                        await self._creds_rotator()
                        self.last_rotated=time.time()
                    else:
                        self.service_status = temp_service
                    break
                except hvac.exceptions.Forbidden:
                    if self.t == 'constant':
                        await asyncio.sleep(self.wait_time)
                    else:
                        await asyncio.sleep( (retry+1)*self.wait_time +self.b)
                
                retry+=1                  

    async def _creds_rotator(self):
        pass

    def check_auth(self):
        if not self.is_connected:
            raise ServiceTemporaryNotAvailableError
        
    @property
    def is_connected(self):
        if self.last_rotated == None:
            return True
        
        return  time.time() - self.last_rotated < self.auth_ttl    


class BrokerService:
    
    def compute_broker_url(self)-> str:
        pass

class ResultBackendService:
    
    def compute_backend_url(self)-> str:
        pass