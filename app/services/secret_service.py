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
from app.utils.constant import VaultConstant
from app.utils.fileIO import FDFlag
from app.utils.helper import b64_decode,b64_encode

# @Service
# class SecretService(BaseService):
    
#     def __init__(self,configService:ConfigService, awsSecretService:AmazonSecretManagerService,hashiVaultService:HashiVaultService):
#         super().__init__()
        
#         self.configService=configService
#         self.awsSecretService = awsSecretService
#         self.hashiVaultService = hashiVaultService
        
DEFAULT_JWT_ALGORITHM = 'HS256'


@Service
class HCVaultService(BaseService,IntervalInterface):
    
    def __init__(self,configService:ConfigService,fileService:FileService):
        super().__init__()
        self.configService = configService
        self.fileService = fileService
        IntervalInterface.__init__(self,False,1000)
        self._jwt_algorithm = self.configService.getenv("JWT_ALGORITHM",DEFAULT_JWT_ALGORITHM)

    def verify_dependency(self):
        ...

    def build(self, build_state = DEFAULT_BUILD_STATE):
        
        if self.configService.MODE == MODE.DEV_MODE:
            self._dev_token_login()
            self.read_tokens()
        else:
            self.client = hvac.Client(self.configService.VAULT_ADDR)
            self.role_id = self._read_volume_file(VaultConstant.ROLE_ID_FILE,'secrets')
            self.secret_id = self._read_volume_file(VaultConstant.SECRET_ID_FILE,'shared')
            seed_time = self._read_volume_file(VaultConstant.SUPERCRONIC_SEED_TIME_FILE,'shared')

            if seed_time and isinstance(seed_time,str):
                self.supercronic_start_time = float(seed_time.split('=')[1])

            self.vault_approle_login()
            print("Lookup key:",self.client.lookup_token())
            self.read_tokens()
                     
    async def callback(self):
        async with self.statusLock.writer as locK:
            self.secret_id = self._read_volume_file(VaultConstant.SECRET_ID_FILE,'shared',False)

##############################################                          ##################################333


    def _read_volume_file(self,filename:str,t:Literal['shared','secrets'],raise_:bool=True):

        callback = VaultConstant.VAULT_SHARED_DIR if t == 'shared' else VaultConstant.VAULT_SECRET_DIR
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

        self.logout()
        self.revoke_auth_token()

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

##############################################                          ##################################333


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

##############################################                          ##################################333

    def renew_auth_token(self):
        self.client.renew_token()

    def revoke_auth_token(self):
        self.client.revoke_token()

    def logout(self):
        self.client.logout()

##############################################                          ##################################333
    
    def read_profile(self,profiles_id:str):
        data = self._kv_read(VaultConstant.PROFILES_SECRETS,profiles_id)
        for k,v in data.items():
            data[k]= self._decrypt_transit(v,VaultConstant.PROFILES_KEY)
        return data

    def put_profiles(self,profiles_id:str,data:dict):
        for k,v in data.items():
            data[k] = self._encrypt_transit(v,VaultConstant.PROFILES_KEY)
        data = {
            profiles_id:data
        }
        return self._kv_put(VaultConstant.PROFILES_SECRETS,profiles_id,data)

    def delete_profiles(self,profiles_id:str):
        return self._kv_delete(VaultConstant.NOTIFYR_SECRETS_MOUNT_POINT,profiles_id)

    def read_tokens(self):
        self.tokens = self._kv_read(VaultConstant.TOKENS_SECRETS)

##############################################                          ##################################333

    def _encrypt_transit(self,plaintext:str,key:VaultConstant.NotifyrTransitKeyType):
        encoded_text = b64_encode(plaintext)
        encrypt_response = self.client.secrets.transit.encrypt_data(
            name=key,
            plaintext=encoded_text,
            mount_point=VaultConstant.NOTIFYR_TRANSIT_MOUNTPOINT
        )
        return encrypt_response["data"]["ciphertext"]
    
    def _decrypt_transit(self,ciphertext:str,key:VaultConstant.NotifyrTransitKeyType):
        decrypted_response = self.client.secrets.transit.decrypt_data(
            name=key,
            ciphertext=ciphertext,
            mount_point=VaultConstant.NOTIFYR_TRANSIT_MOUNTPOINT
        )
        encoded_response = decrypted_response['data']['plaintext']
        return b64_decode(encoded_response)
    
    def _kv_read(self,sub_mount:VaultConstant.NotifyrSecretType,path:str=''):
        read_response = self.client.secrets.kv.v1.read_secret(
        path=VaultConstant.KV_ENGINE_BASE_PATH(sub_mount,path),
        mount_point=VaultConstant.NOTIFYR_SECRETS_MOUNT_POINT,
        )
        if 'data' in read_response:
            return read_response['data']
        return {}

    def _kv_put(self,sub_mount:VaultConstant.NotifyrSecretType,data:dict,path:str=''):
        self.client.secrets.kv.v1.create_or_update_secret(
        path=VaultConstant.KV_ENGINE_BASE_PATH(sub_mount,path),
        secret=data,
        mount_point=VaultConstant.NOTIFYR_SECRETS_MOUNT_POINT,)
    
    def _kv_delete(self,sub_mount:VaultConstant.NotifyrSecretType,path:str):
        return self.client.secrets.kv.v1.delete_secret(
            path=VaultConstant.KV_ENGINE_BASE_PATH(sub_mount,path),
            mount_point=VaultConstant.NOTIFYR_SECRETS_MOUNT_POINT
                )

##############################################                          ##################################333

    @property
    def JWT_SECRET_KEY(self):
        return self.tokens.get('JWT_SECRET_KEY',None)
    
    @property
    def JWT_ALGORITHM(self):
        return self._jwt_algorithm

    @property
    def ON_TOP_SECRET_KEY(self):
        return self.tokens.get('ON_TOP_SECRET_KEY',None)
    
    @property
    def API_ENCRYPT_TOKEN(self):
        return self.tokens.get('API_ENCRYPT_TOKEN',None)
    
    @property
    def CONTACTS_HASH_KEY(self):
        return self.tokens.get('CONTACTS_HASH_KEY',None)
    
    @property
    def CONTACT_JWT_SECRET_KEY(self):
        return self.tokens.get('CONTACT_JWT_SECRET_KEY')
    
    @property
    def CLIENT_PASSWORD_HASH_KEY(self):
        return self.tokens.get('CLIENT_PASSWORD_HASH_KEY',None)
    
    @property
    def RSA_PASSWORD(self):
        return self.tokens.get('RSA_PASSWORD',None)


    
