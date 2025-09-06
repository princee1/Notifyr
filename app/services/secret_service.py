from typing import Literal

import requests
from app.definition._service import DEFAULT_BUILD_STATE, DEFAULT_DESTROY_STATE, BaseService, BuildAbortError, Service, ServiceStatus
from app.interface.timers import IntervalInterface
from app.services.aws_service import AmazonSecretManagerService
from app.services.config_service import MODE, ConfigService
from pathlib import Path
from app.services.database_service import RedisService
import hvac
from os import system

from app.services.file_service import FileService
from app.utils.fileIO import FDFlag

# @Service
# class SecretService(BaseService):
    
#     def __init__(self,configService:ConfigService, awsSecretService:AmazonSecretManagerService,hashiVaultService:HashiVaultService):
#         super().__init__()
        
#         self.configService=configService
#         self.awsSecretService = awsSecretService
#         self.hashiVaultService = hashiVaultService
        

def VAULT_SECRET_DIR(file:str)->str:
    return f'../../vault/secrets/{file}'

def VAULT_SHARED_DIR(file:str)->str:
    return f'../../vault/shared/{file}'


SECRET_ID_FILE= 'secret-id.txt' 
ROLE_ID_FILE = 'role_id.txt' # in the secrets shared by the vault
SUPERCRONIC_SEED_TIME_FILE = 'seed-time.txt'




@Service
class HCVaultService(BaseService,IntervalInterface):
    
    def __init__(self,configService:ConfigService,fileService:FileService):
        super().__init__()
        self.configService = configService
        self.fileService = fileService
        IntervalInterface.__init__(self,False,1000)

    def verify_dependency(self):
        ...

    def build(self, build_state = DEFAULT_BUILD_STATE):
        
        if self.configService.MODE == MODE.DEV_MODE:
            self._dev_token_login()
        else:
            self.client = hvac.Client(self.configService.VAULT_ADDR)
            self.role_id = self._read_volume_file(ROLE_ID_FILE,'secrets')
            self.secret_id = self._read_volume_file(SECRET_ID_FILE,'shared')
            self.supercronic_start_time = self._read_volume_file(SUPERCRONIC_SEED_TIME_FILE,'shared')
            self.vault_approle_login()
            
    async def callback(self):
        async with self.statusLock.writer as locK:
            self.secret_id = self._read_volume_file(SECRET_ID_FILE,'shared',False)

    def _read_volume_file(self,filename:str,t:Literal['shared','secrets'],raise_:bool=True):

        callback = VAULT_SHARED_DIR if t == 'shared' else VAULT_SECRET_DIR
        filename_ = callback(filename)
        content:str = self.fileService.readFile(filename_,FDFlag.READ)
        _,last_modified = self.fileService.get_file_info(filename_)
        
        if content != None:
            return content.strip()
        else:
            if raise_:
                raise BuildAbortError(f'Could not get the {filename}')

        return content

    def destroy(self, destroy_state = DEFAULT_DESTROY_STATE):
        self.client.logout()

    def vault_approle_login(self):
        try:
            if not self._vault_auth():
                raise BuildAbortError('Not authenticated')
            
            if not self.client.ha_status['is_self']:
                self.service_status = ServiceStatus.PARTIALLY_AVAILABLE

            if not self.client.seal_status['initialized']:
                raise BuildAbortError('Vault Db is not initialized')
            
            if self.client.seal_status['sealed']:
                raise BuildAbortError('Cant access vault since it sealed')
            
        except hvac.exceptions.InvalidRequest as e:
            raise BuildAbortError(f'"Invalid:", {e}')
        except hvac.exceptions.InternalServerError as e:
            raise BuildAbortError(f"IntervalServerError {e}")
        except hvac.exceptions.Forbidden as e:
            raise BuildAbortError(f"Forbidden: {e}")
        except hvac.exceptions.Unauthorized as e:
            raise BuildAbortError(f"Unauthorized: {e}")
        except requests.exceptions.ConnectionError as e:
            raise BuildAbortError(f"Vault server not reachable: {e}")
        except requests.exceptions.Timeout as e:
            raise BuildAbortError("Vault request timed out: {e}")

    def vault_auth(self):
        if not self._vault_auth():
            self.service_status = ServiceStatus.NOT_AVAILABLE

    def _vault_auth(self):
        self.client.auth.approle.login(self.role_id,self.secret_id)
        return self.client.is_authenticated()
  
    def _dev_token_login(self):
        try:
            ...
        except:
            ...

    def delete(self):
        self.client
    
    def list(self):
        ...
    
    def read(self):
        self.client
    
    def write(self):
        self.client

    @property
    def JWT_SECRET_KEY(self):
        return 
    
    @property
    def JWT_ALGORITHM(self):
        ...

    @property
    def ON_TOP_SECRET_KEY(self):
        ...
    
    @property
    def API_ENCRYPT_TOKEN(self):
        ...
    
    @property
    def CONTACTS_HASH_KEY(self):
        ...
    
    @property
    def CONTACT_JWT_SECRET_KEY(self):
        ...
    
    @property
    def CLIENT_PASSWORD_HASH_KEY(self):
        ...
    
    @property
    def RSA_PASSWORD(self):
        ...



    
