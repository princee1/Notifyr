
from cachetools import cached,TTLCache
from typing import Any, Dict, Literal
from app.classes.secrets import ChaCha20SecretsWrapper
from app.definition._interface import Interface, IsInterface
from app.errors.service_error import BuildWarningError
from app.services.setting_service import SettingService
from app.utils.constant import VaultConstant
from app.utils.fileIO import FDFlag
from app.utils.tools import Cache, RunInThreadPool, Time
from .config_service import ConfigService
from .file.file_service import FileService
from app.definition._service import AbstractServiceClass, BaseService, BuildFailureError, Service, ServiceStatus
import jwt
import base64
from fastapi import HTTPException, Request, status
import time
from app.classes.auth_permission import AuthPermission, ClientType, ContactPermission, ContactPermissionScope, RefreshPermission, Role, RoutePermission, Scope, WSPermission
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

    def _encode_value(self, value: str, key: bytes | str) -> str:
        key = key.encode()
        value = base64.b64encode(value.encode()).decode()
        cipher = ChaCha20SecretsWrapper(value,key,self.nonce)
        return cipher.cipher_data.decode()

    @Time
    def _decode_value(self, value: str, key: bytes | str) -> str:
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

    def encode_auth_token(self,authz_id, client_id:str, challenge: str, group_id: str | None) -> str:
        try:
            salt = str(self.salt)
            created_time = time.time()
            permission = AuthPermission(generation_id=self.GENERATION_ID, created_at=created_time,expired_at=created_time + self.settingService.AUTH_EXPIRATION*0.5,
                                        salt=salt, group_id=group_id, challenge=challenge,client_id=client_id,
                                        authz_id=authz_id)
            token = self._encode_token(permission)
            return token
        except Exception as e:
            print(e)
        return None

    def encode_refresh_token(self,client_id:str,challenge: str, group_id:str):
        try:
            salt = str(self.salt)
            created_time = time.time()
            permission = RefreshPermission(client_id=client_id, generation_id=self.GENERATION_ID, created_at=created_time, salt=salt, challenge=challenge,
                                           expired_at=created_time + self.settingService.REFRESH_EXPIRATION*0.5,group_id=group_id)
            token = self._encode_token(permission)
            return token
        except Exception as e:
            print(e)
        return None

    def set_status(self, permission: AuthPermission | RefreshPermission, ptype: Literal['auth', 'refresh']):
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
        return self._encode_token(permission, self.vaultService.CONTACT_JWT_SECRET_KEY,False)

    def _encode_token(self, obj, secret_key: str = None, lookup=True):
        if secret_key == None:
            secret_key = self.vaultService.JWT_SECRET_KEY
        else:
            if lookup:
                secret_key = self.vaultService.tokens.get(secret_key,self.vaultService.JWT_SECRET_KEY)

        encoded = jwt.encode(obj, secret_key, algorithm=self.vaultService.JWT_ALGORITHM)
        token = self._encode_value(encoded, self.vaultService.ON_TOP_SECRET_KEY)
        return token

    @cached(TTLCache(50,60*60*3))
    def _decode_token(self, token: str, secret_key: str = None) -> dict:
        try:
            if secret_key == None:
                secret_key = self.vaultService.JWT_SECRET_KEY
            else:
                secret_key = self.vaultService.tokens(secret_key, self.vaultService.JWT_SECRET_KEY)

            token = self._decode_value(token, self.vaultService.ON_TOP_SECRET_KEY)
            decoded = jwt.decode(token, secret_key,algorithms=self.vaultService.JWT_ALGORITHM)
            return decoded

        # TODO: For each exception, we should return a specific error message

        except jwt.InvalidSignatureError as e:
            ...
        except jwt.InvalidAlgorithmError as e:

            ...
        except jwt.InvalidKeyError as e:

            ...
        except jwt.ExpiredSignatureError as e:

            ...
        except jwt.InvalidTokenError as e:
            ...
        except Exception as e:
            ...

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")

    def verify_client_origin(self,permission:AuthPermission,issued_for,origin=None):
        match permission['scope']:
            case Scope.SoloDolo:
                if issued_for != permission["issued_for"]:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Token not issued for this user")
            case Scope.Organization:
                # TODO verify subnet
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Token not issued for this user")
            case Scope.Domain:
                if origin == None:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Origin header missing")
            
            case Scope.Free:
                ...
                
    def verify_auth_permission(self, token: str, issued_for: str) -> AuthPermission:

        token = self._decode_token(token)
        permission: AuthPermission = AuthPermission(**token)
        try:

            self.set_status(permission,'auth')
            # if permission['status'] == 'expired': # NOTE might accept expired
            #     raise HTTPException(
            #         status_code=status.HTTP_403_FORBIDDEN,  detail="Token expired")

            if permission["generation_id"] != self.GENERATION_ID:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Old Token not valid anymore")
            return permission
        except KeyError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail='Data missing')

    def verify_refresh_permission(self,tokens:str):
        token =self._decode_token(tokens)
        permission = RefreshPermission(**token)
        self.set_status(permission,'refresh')

        if permission['status'] == 'expired':
            raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,  detail="Token expired")
        
        return permission

    def verify_contact_permission(self, token: str) -> ContactPermission:

        token = self._decode_token(token, 'CONTACT_JWT_SECRET_KEY')
        permission: ContactPermission = ContactPermission(**token)

        try:
            if permission["expired_at"] < time.time():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,  detail="Token expired")
        except KeyError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail='Data missing')

    def read_generation_id(self):
        data=self.vaultService.generation_engine.read('',self.gen_id_path)
        self.generation_id_data = data

    @RunInThreadPool
    def revoke_all_tokens(self) -> None:
        new_generation_id = generateId(self.GENERATION_ID_LEN)
        self.vaultService.generation_engine.put('',{
            'GENERATION_ID':new_generation_id,
        },path=self.gen_id_path)
        self.read_generation_id()
    
    @RunInThreadPool
    def unrevoke_all_tokens(self,version:int|None,destroy:bool,delete:bool,version_to_delete:list[int]=[]):
        self.vaultService.generation_engine.rollback('',self.gen_id_path,version,destroy,delete,version_to_delete)
        self.read_generation_id()

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
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,detail='Could not retrieve the api key')

        if token != self.API_KEY:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Api Key provided does not match the one given")

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

        
    def hash_value_with_salt(self, value, key, salt):
        value_with_salt = value.encode() + salt
        hmac_obj = hmac.new(key.encode(), value_with_salt, hashlib.sha256)
        return hmac_obj.hexdigest()

    def store_password(self, password, key):
        salt = generate_salt()
        hashed_password = self.hash_value_with_salt(password, key, salt)
        # salt = b64_encode(salt)
        hashed_password = b64_encode(hashed_password)
        return hashed_password, salt

    def verify_password(self, stored_hash, stored_salt, provided_password, key):
        stored_hash = b64_decode(stored_hash)
        stored_salt = bytes(stored_salt.encode())
        # stored_salt = b64_decode(stored_salt)
        hashed_provided_password = self.hash_value_with_salt(provided_password, key, stored_salt)
        return hmac.compare_digest(stored_hash, hashed_provided_password)
    
    def verify_admin_signature(self,):
        ...
    