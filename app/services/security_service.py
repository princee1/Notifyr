
from cachetools import cached,TTLCache
from typing import Any, Dict, Literal
from app.classes.secrets import ChaCha20SecretsWrapper
from app.definition._interface import Interface, IsInterface
from app.errors.security_error import (
    APIKeyMismatchError,
    APIKeyMissingError,
    JWTInvalidTokenError,
    ProvidedHashNotEquivalentError,
    TokenDataMissingError,
    TokenExpiredError,
    TokenGenerationMismatchError,
)
from app.errors.service_error import BuildWarningError
from app.services.setting_service import SettingService
from app.utils.constant import VaultConstant
from app.utils.fileIO import FDFlag
from app.utils.toolbox import Cache, RunInThreadPool, Time
from .config_service import ConfigService
from .file.file_service import FileService
from app.definition._service import AbstractServiceClass, BaseService, BuildFailureError, Service, ServiceStatus
import jwt
import base64
import time
from app.classes.auth_permission import AuthPermission, AuthType, ClientAccessInfo, ClientType, ContactPermission, ContactPermissionScope, ClientRefresh, Role, RoutePermission, Scope, WSPermission
from random import randint, random
from app.utils.helper import generateId, b64_encode, b64_decode
import os
import hmac
import hashlib
from app.services.vault_service import VaultService


SEPARATOR = "|"
ID_LENGTH = 25


def generate_salt(length=64):
    return os.urandom(length)


@IsInterface
class EncryptDecryptInterface(Interface):

    def __init__(self,nonce:str):
        self.nonce = nonce.encode()

    def _encode_value(self, value: str, key: bytes | str,wrapper=False) -> str:
        if not wrapper:
            return value
        key = key.encode()
        value = base64.b64encode(value.encode()).decode()
        cipher = ChaCha20SecretsWrapper(value,key,self.nonce)
        return cipher.cipher_data.decode()

    @Time
    def _decode_value(self, value: str, key: bytes | str,wrapper=False) -> str:
        if not wrapper:
            return value
        key = key.encode()
        cipher = ChaCha20SecretsWrapper(value,key,self.nonce)
        cipher.cipher_data = value
        value = cipher.to_plain()
        return base64.b64decode(value).decode()
    

    @property
    def salt(self):
        return generate_salt()


@Service()
class JWTAuthService(BaseService, EncryptDecryptInterface):
    GENERATION_ID_LEN = 32
    gen_id_path='generation-id'
    NONCE="1234567891234578"

    def __init__(self, configService: ConfigService, fileService: FileService,settingService:SettingService,vaultService:VaultService) -> None:
        super().__init__()
        EncryptDecryptInterface.__init__(self,self.NONCE)
        self.configService = configService
        self.fileService = fileService
        self.settingService = settingService
        self.vaultService = vaultService

    def encode_auth_token(self,signature:str, client_id:str,auth_type:AuthType)->str:
        try:
            salt = str(self.salt)
            exp = self.settingService.API_EXPIRATION if auth_type == AuthType.API_TOKEN else self.settingService.AUTH_EXPIRATION
            created_time = time.time()
            permission = ClientAccessInfo(generation_id=self.GENERATION_ID, created_at=created_time,expired_at=created_time + exp,
                                        salt=salt,client_id=client_id,auth_signature=signature)
            token = self._encode_token(permission,)
            return token
        except Exception as e:
            print(e)
        return None

    def encode_refresh_token(self,signature:str,client_id:str):
        try:
            salt = str(self.salt)
            created_time = time.time()
            permission = ClientRefresh(client_id=client_id,auth_signature=signature, generation_id=self.GENERATION_ID, created_at=created_time, salt=salt,
                                           expired_at=created_time + self.settingService.REFRESH_EXPIRATION)
            token = self._encode_token(permission)
            return token
        except Exception as e:
            print(e)
        return None

    def set_status(self, permission: AuthPermission | ClientRefresh, ptype: Literal['auth', 'refresh']):
        now = time.time()
        expired_at = permission['expired_at']
        created_at = permission['created_at']

        diff = expired_at - now

        if diff < 0:
            permission['status'] = 'expired'
            return

        total_lifetime = expired_at - created_at
        elapsed_time = now - created_at

        if elapsed_time > total_lifetime * 0.8:
            permission['status'] = 'inactive'
            return

        permission['status'] = 'active'
        return
                
    def encode_ws_token(self, run_id: str, operation_id: str, expiration: float):
        now = time.time()
        expired_at = now + expiration
        salt = str(self.salt)
        permission = WSPermission(
            operation_id=operation_id, expired_at=expired_at, created_at=now, run_id=run_id, salt=salt)
        return self._encode_token(permission, self.vaultService.WS_JWT_SECRET_KEY,False)

    def encode_contact_token(self, contact_id: str, expiration: float, scope: ContactPermissionScope):
        now = time.time()
        expiration = now + expiration
        salt = str(self.salt)
        permission = ContactPermission(
            expired_at=expiration, create_at=now, scope=scope, contact_id=contact_id, salt=salt)
        return self._encode_token(permission, self.vaultService.CONTACT_JWT_SECRET_KEY,True)

    def _encode_token(self, obj, secret_key: str = None, lookup=True,wrapper=False):
        if secret_key == None:
            secret_key = self.vaultService.JWT_SECRET_KEY
        else:
            if lookup:
                secret_key = self.vaultService.tokens.get(secret_key,self.vaultService.JWT_SECRET_KEY)

        encoded = jwt.encode(obj, secret_key, algorithm=self.vaultService.JWT_ALGORITHM)
        token = self._encode_value(encoded, self.vaultService.ON_TOP_SECRET_KEY,wrapper=wrapper)
        return token

    #@cached(TTLCache(50,60*60*3))
    def _decode_token(self, token: str, secret_key: str = None,wrapper=False) -> dict:
        try:
            if secret_key == None:
                secret_key = self.vaultService.JWT_SECRET_KEY
            else:
                secret_key = self.vaultService.tokens.get(secret_key, self.vaultService.JWT_SECRET_KEY)

            token = self._decode_value(token, self.vaultService.ON_TOP_SECRET_KEY,wrapper=wrapper)
            decoded = jwt.decode(token, secret_key,algorithms=self.vaultService.JWT_ALGORITHM)
            return decoded

        except jwt.InvalidSignatureError as e:
            raise JWTInvalidTokenError(token=token, reason='invalid signature') from e
        except jwt.InvalidAlgorithmError as e:
            raise JWTInvalidTokenError(token=token, reason='invalid algorithm') from e
        except jwt.InvalidKeyError as e:
            raise JWTInvalidTokenError(token=token, reason='invalid signing key') from e
        except jwt.ExpiredSignatureError as e:
            raise TokenExpiredError(token=token, token_type='token', reason='expired signature') from e
        except jwt.InvalidTokenError as e:
            raise JWTInvalidTokenError(token=token, reason='invalid token') from e
        except Exception as e:
            raise JWTInvalidTokenError(token=token, reason=str(e)) from e
                
    def verify_client_token_permission(self, token: str,raise_on_expired=False) -> ClientAccessInfo:

        decoded = self._decode_token(token)
        clientInfo: ClientAccessInfo = ClientAccessInfo(**decoded)
        try:
            if clientInfo["generation_id"] != self.GENERATION_ID:
                raise TokenGenerationMismatchError(
                    expected_generation_id=self.GENERATION_ID,
                    actual_generation_id=clientInfo["generation_id"],
                    token_type='auth',
                )

            self.set_status(clientInfo,'auth')
            if clientInfo['status'] == 'expired' and raise_on_expired:
                raise TokenExpiredError(token=token, token_type='auth', reason='auth token expired')

            return clientInfo
        except KeyError as e:
            raise TokenDataMissingError(missing_fields=['generation_id', 'expired_at', 'created_at'], token=token) from e

    def verify_refresh_permission(self,tokens:str,raise_on_expired:bool=False):
        decoded = self._decode_token(tokens)
        permission = ClientRefresh(**decoded)

        if permission["generation_id"] != self.GENERATION_ID:
                    raise TokenGenerationMismatchError(
                        expected_generation_id=self.GENERATION_ID,
                        actual_generation_id=permission["generation_id"],
                        token_type='refresh',
                    )
        
        self.set_status(permission,'refresh')
        if permission['status'] == 'expired' and raise_on_expired:
            raise TokenExpiredError(token=tokens, token_type='refresh', reason='refresh token expired')

        return permission

    def verify_contact_permission(self, token: str) -> ContactPermission:

        decoded = self._decode_token(token, 'CONTACT_JWT_SECRET_KEY',True)
        permission: ContactPermission = ContactPermission(**decoded)

        try:
            if permission["expired_at"] < time.time():
                raise TokenExpiredError(token=token, token_type='contact', reason='contact token expired')
            return permission
        except KeyError as e:
            raise TokenDataMissingError(missing_fields=['expired_at'], token=token) from e

    def read_generation_id(self):
        data=self.vaultService.generation_engine.read('',self.gen_id_path)
        self.generation_id_data = data

    def verify_dependency(self):
        if self.vaultService.service_status not in {ServiceStatus.AVAILABLE,ServiceStatus.PARTIALLY_AVAILABLE}:
            raise BuildFailureError

    def build(self,build_state=-1):
        self.read_generation_id()
        if self.GENERATION_ID == None:
            raise BuildFailureError

    @property
    def GENERATION_ID(self)->None|str:
        return self.generation_id_data.get('data',{}).get('GENERATION_ID',None)

    @property
    def GENERATION_METADATA(self)->dict:
        return self.generation_id_data.get('metadata',{})

@Service()
class SecurityService(BaseService, EncryptDecryptInterface):
    NONCE="1234567891234578"

    def __init__(self, configService: ConfigService, fileService: FileService,settingService:SettingService,vaultService:VaultService) -> None:
        super().__init__()
        EncryptDecryptInterface.__init__(self,self.NONCE)
        self.configService = configService
        self.fileService = fileService
        self.settingService= settingService
        self.vaultService = vaultService

        self.API_KEY:str = ...

    def verify_server_access(self, token: str) -> bool:
        if not self.API_KEY:
            raise APIKeyMissingError(source='server_api_key')

        if token != self.API_KEY:
            raise APIKeyMismatchError(source='server_api_key', provided=token)

        return True

    def build(self,build_state=-1):
        api_key = self.fileService.readFile('/run/secrets/api_key.txt',flag=FDFlag.READ)
        if api_key == None:
            raise BuildWarningError()
        
        self.API_KEY = api_key
        try:
            self.DMZ_KEY=self.vaultService.secrets_engine.read(VaultConstant.INTERNAL_API_SECRETS,'DMZ')['API_KEY']
            self.BALANCER_EXCHANGE_TOKEN=self.vaultService.secrets_engine.read(VaultConstant.INTERNAL_API_SECRETS,'BALANCER')['API_KEY']
            self.DASHBOARD_KEY=self.vaultService.secrets_engine.read(VaultConstant.INTERNAL_API_SECRETS,'DASHBOARD')['API_KEY']
        except Exception as e:
            print(e)
            raise BuildWarningError()

    def hash(self, value:str, key:str, salt:bytes|str=None,algorithm=None):
        if salt == None:
            salt = generateId(8)
            salt = salt.encode()
        elif isinstance(salt,str):
            salt = salt.encode()
        else:
            ...
        value_with_salt = value.encode() + salt
        hmac_obj = hmac.new(key.encode(), value_with_salt, hashlib.sha256)
        return hmac_obj.hexdigest(),salt.decode()

    def compare_hash(self, stored_hash:str,provided:str,key:str,salt:bytes|str=None,algorithm=None):
        provided_hash,_ = self.hash(provided,key,salt)
        if not hmac.compare_digest(stored_hash, provided_hash):
            raise ProvidedHashNotEquivalentError(provided_hash,'hashed value')
        return True

    def simple_hash(self,value:str):
        return
    
    def verify_admin_signature(self,):
        ...
    