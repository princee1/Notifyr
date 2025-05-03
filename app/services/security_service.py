
from typing import Any, Dict, Literal

from app.classes.rsa import RSA
from app.definition._interface import Interface, IsInterface
from .config_service import ConfigService
from dataclasses import dataclass
from .file_service import FileService
from app.definition._service import AbstractServiceClass, Service, ServiceClass
import jwt
from cryptography.fernet import Fernet, InvalidToken
import base64
from fastapi import HTTPException, status
import time
from app.classes.auth_permission import AuthPermission, ClientType, ContactPermission, ContactPermissionScope, RefreshPermission, Role, RoutePermission, Scope, WSPermission
from random import randint, random
from app.utils.helper import generateId, b64_encode, b64_decode
from app.utils.constant import ConfigAppConstant
from datetime import datetime, timezone
import os
import hmac
import hashlib


SEPARATOR = "|"
ID_LENGTH = 25


def generate_salt(length=64):
    return os.urandom(length)


@IsInterface
class EncryptDecryptInterface(Interface):

    def _encode_value(self, value: str, key: bytes | str) -> str:
        value = base64.b64encode(value.encode()).decode()
        cipher_suite = Fernet(key)
        return cipher_suite.encrypt(value.encode()).decode()

    def _decode_value(self, value: str, key: bytes | str) -> str:
        cipher_suite = Fernet(key)
        value = cipher_suite.decrypt(value.encode())
        return base64.b64decode(value).decode()

    @property
    def salt(self):
        return generate_salt()


@ServiceClass
class JWTAuthService(Service, EncryptDecryptInterface):
    def __init__(self, configService: ConfigService, fileService: FileService) -> None:
        super().__init__()
        self.configService = configService
        self.fileService = fileService

    def set_generation_id(self, gen=False) -> None:
        if gen:
            self.generation_id = generateId(ID_LENGTH)
            self.configService.config_json_app.data[ConfigAppConstant.META_KEY][
                ConfigAppConstant.GENERATION_ID_KEY] = self.generation_id
            current_utc = datetime.now(timezone.utc)
            expired_ = current_utc.timestamp() + self.configService.ALL_ACCESS_EXPIRATION
            expired_utc = datetime.fromtimestamp(expired_, timezone.utc)
            self.configService.config_json_app.data[ConfigAppConstant.META_KEY][ConfigAppConstant.CREATION_DATE_KEY] = current_utc.strftime(
                "%Y-%m-%d %H:%M:%S")
            self.configService.config_json_app.data[ConfigAppConstant.META_KEY][ConfigAppConstant.EXPIRATION_DATE_KEY] = expired_utc.strftime(
                "%Y-%m-%d %H:%M:%S")
            self.configService.config_json_app.data[ConfigAppConstant.META_KEY][
                ConfigAppConstant.EXPIRATION_TIMESTAMP_KEY] = expired_
            self.configService.config_json_app.save()

        else:
            self.generation_id = self.configService.config_json_app.data[
                ConfigAppConstant.META_KEY][ConfigAppConstant.GENERATION_ID_KEY]

    def encode_auth_token(self,authz_id,client_type:ClientType, client_id:str, scope: str, data: Dict[str, RoutePermission], challenge: str, roles: list[str], group_id: str | None, issue_for: str, hostname,allowed_assets: list[str] = []) -> str:
        try:
            if data == None:
                data = {}
            salt = str(self.salt)
            created_time = time.time()
            permission = AuthPermission(client_type=client_type.value,scope=scope, generation_id=self.generation_id, issued_for=issue_for, created_at=created_time,
                                        expired_at=created_time + self.configService.AUTH_EXPIRATION*0.5, allowed_routes=data, roles=roles, allowed_assets=allowed_assets,
                                        salt=salt, group_id=group_id, challenge=challenge,hostname=hostname,client_id=client_id,authz_id=authz_id)
            token = self._encode_token(permission)
            return token
        except Exception as e:
            print(e)
        return None

    def encode_refresh_token(self,client_id:str, issued_for: str, challenge: str, group_id:str,client_type:ClientType):
        try:
            salt = str(self.salt)
            created_time = time.time()
            permission = RefreshPermission(client_id=client_id, generation_id=self.generation_id, issued_for=issued_for, created_at=created_time, salt=salt, challenge=challenge,
                                           expired_at=created_time + self.configService.REFRESH_EXPIRATION*0.5,group_id=group_id,client_type=client_type.value)
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
        return self._encode_token(permission, 'WS_JWT_SECRET_KEY')

    def encode_contact_token(self, contact_id: str, expiration: float, scope: ContactPermissionScope):
        now = time.time()
        expiration = now + expiration
        salt = str(self.salt)
        permission = ContactPermission(
            expired_at=expiration, create_at=now, scope=scope, contact_id=contact_id, salt=salt)
        return self._encode_token(permission, 'CONTACT_JWT_SECRET_KEY')

    def _encode_token(self, obj, secret_key: str = None):
        if secret_key == None:
            secret_key = self.configService.JWT_SECRET_KEY
        else:
            secret_key = self.configService.getenv(
                secret_key, self.configService.JWT_SECRET_KEY)
        encoded = jwt.encode(
            obj, secret_key, algorithm=self.configService.JWT_ALGORITHM)
        token = self._encode_value(
            encoded, self.configService.ON_TOP_SECRET_KEY)
        return token

    def decode_token(self, token: str, secret_key: str = None) -> dict:
        try:
            if secret_key == None:
                secret_key = self.configService.JWT_SECRET_KEY
            else:
                secret_key = self.configService.getenv(
                    secret_key, self.configService.JWT_SECRET_KEY)

            token = self._decode_value(
                token, self.configService.ON_TOP_SECRET_KEY)
            decoded = jwt.decode(token, self.configService.JWT_SECRET_KEY,
                                 algorithms=self.configService.JWT_ALGORITHM)
            return decoded

        # TODO: For each exception, we should return a specific error message

        except InvalidToken as e:
            ...

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

    def verify_auth_permission(self, token: str, issued_for: str) -> AuthPermission:

        token = self.decode_token(token)
        permission: AuthPermission = AuthPermission(**token)
        try:
            if permission['scope'] == Scope.SoloDolo.value:
                if issued_for != permission["issued_for"]:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Token not issued for this user")
            else:
                # TODO verify subnet
                ...

            self.set_status(permission,'auth')
            # if permission['status'] == 'expired': # NOTE might accept expired
            #     raise HTTPException(
            #         status_code=status.HTTP_403_FORBIDDEN,  detail="Token expired")

            if permission["generation_id"] != self.generation_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Old Token not valid anymore")
            return permission
        except KeyError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail='Data missing')

    def verify_refresh_permission(self,tokens:str):
        token =self.decode_token(tokens)
        permission = RefreshPermission(**token)
        self.set_status(permission,'refresh')

        if permission['status'] == 'expired':
            raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,  detail="Token expired")
        
        return permission

    def verify_contact_permission(self, token: str) -> ContactPermission:

        token = self.decode_token(token, 'CONTACT_JWT_SECRET_KEY')
        permission: ContactPermission = ContactPermission(**token)

        try:
            if permission["expired_at"] < time.time():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,  detail="Token expired")
        except KeyError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail='Data missing')

    def build(self):
        ...


@ServiceClass
class SecurityService(Service, EncryptDecryptInterface):

    def __init__(self, configService: ConfigService, fileService: FileService) -> None:
        super().__init__()
        self.configService = configService
        self.fileService = fileService

    def verify_server_access(self, token: str, sent_ip_addr) -> bool:
        token = self._decode_value(token, self.configService.API_ENCRYPT_TOKEN)
        token = token.split("|")

        if len(token) != 3:
            return False
        ip_addr = token[0]

        if ip_addr != sent_ip_addr:
            return False

        if time.time() - float(token[1]) > self.configService.API_EXPIRATION:
            return False

        if token[2] != self.configService.API_KEY:
            return False

        return True

    def generate_custom_api_key(self, ip_address: str):
        time.sleep(random()/100)
        data = ip_address + SEPARATOR +  \
            str(time.time_ns()) + SEPARATOR + self.configService.API_KEY
        return self._encode_value(data, self.configService.API_ENCRYPT_TOKEN)

    def build(self):
        ...

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

    def generate_key_pair(self,key_size=512):
        rsa_secret_pwd = self.configService.getenv('RSA_SECRET_PASSWORD','test')
        return RSA(key_size=key_size,password=rsa_secret_pwd)
        
    