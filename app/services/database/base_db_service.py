
import asyncio
from random import randint, random
import time
import hvac
from typing_extensions import Literal
from app.classes.vault_engine import VaultDatabaseCredentials
from app.definition._service import AbstractServiceClass, BaseService, ServiceStatus
from app.errors.service_error import BuildFailureError, ServiceTemporaryNotAvailableError
from app.interface.timers import IntervalParams, SchedulerInterface
from app.services.config_service import ConfigService
from app.services.file.file_service import FileService
from app.services.vault_service import VaultService


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
        self.creds:VaultDatabaseCredentials = {}
        self.max_retry = max_retry
        self.wait_time = wait_time
        self.t=t
        self.b = b
        self.last_rotated = None
        self.auth_ttl = ttl

    def build(self, build_state = ...):
        delay = IntervalParams( seconds=self.random_buffer_interval(self.auth_ttl) )
        self.interval_schedule(delay, self.creds_rotation,tuple(),{},f"{self.name}-creds_rotation")

    def verify_dependency(self):
        if self.vaultService.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError("Vault Service can’t issue creds")

    async def pingService(self,infinite_wait:bool,data:dict,profile:str=None,as_manager:bool=False,**kwargs):
        self.check_auth()
        await super().pingService(infinite_wait,data,profile,as_manager,**kwargs)
             
    @staticmethod
    def random_buffer_interval(ttl):
        return ttl - (ttl*.08*random() + randint(20,40))

    def renew_db_creds(self):
        lease_id = self.creds['lease_id']
        self.vaultService.renew_lease(lease_id,3600)
    
    @property
    def db_user(self):
        return self.creds.get('data',dict()).get('username',None)
        
    @property
    def db_password(self):
        return self.creds.get('data',dict()).get('password',None)

    @property
    def lease_id(self):
        return self.creds.get('lease_id',None)
    
    def revoke_lease(self):
        return self.vaultService.revoke_lease(self.lease_id)

    async def _check_vault_status(self):
        temp_service = None 
        async with self.vaultService.statusLock.reader:
            if self.vaultService.service_status == ServiceStatus.AVAILABLE:
                ...
            else: 
                temp_service = self.vaultService.service_status
        return temp_service

    async def creds_rotation(self):
        temp_service = await self._check_vault_status()
        async with self.statusLock.writer:

            retry =0
            while retry<self.max_retry:
                try:
                    if temp_service == None:
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
