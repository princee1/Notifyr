
from typing import Any, Dict

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
from app.classes.auth_permission import AuthPermission, Role, RoutePermission
from random import randint, random
from app.utils.helper import generateId
from app.utils.constant import ConfigAppConstant
from datetime import datetime, timezone


SEPARATOR = "|"
ID_LENGTH = 25


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
            self.configService.config_json_app.data[ConfigAppConstant.META_KEY][ConfigAppConstant.EXPIRATION_DATE_KEY] = expired_utc.strftime("%Y-%m-%d %H:%M:%S")
            self.configService.config_json_app.data[ConfigAppConstant.META_KEY][ConfigAppConstant.EXPIRATION_TIMESTAMP_KEY] = expired_
            self.configService.config_json_app.save()

        else:
            self.generation_id = self.configService.config_json_app.data[
                ConfigAppConstant.META_KEY][ConfigAppConstant.GENERATION_ID_KEY]

    def encode_auth_token(self,data: Dict[str, RoutePermission],roles:list[str], issue_for: str,) -> str:
        try:
            if data==None:
                data = {}
            created_time = time.time()
            permission = AuthPermission(generation_id=self.generation_id, issued_for=issue_for, created_at=created_time,
                                        expired_at=created_time + self.configService.AUTH_EXPIRATION, allowed_routes=data,roles=roles)
            token = self._encode_token(permission)
            return token
        except Exception as e:
            print(e)
        return None
    

    def encode_temporary_token(self,):
        ...

    def _encode_token(self, obj):
        encoded = jwt.encode(obj, self.configService.JWT_SECRET_KEY,
                                 algorithm=self.configService.JWT_ALGORITHM)
        token = self._encode_value(encoded, self.configService.ON_TOP_SECRET_KEY)
        return token

    def decode_token(self, token: str) -> dict:
        try:
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

    def verify_permission(self, token: str,issued_for: str) -> AuthPermission:

        token = self.decode_token(token)
        permission: AuthPermission = AuthPermission(**token)
        try:
            if issued_for != permission["issued_for"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Token not issued for this user")

            if permission["expired_at"] < time.time():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,  detail="Token expired")

            if permission["generation_id"] != self.generation_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Old Token not valid anymore")
            return permission
        except KeyError as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='Data missing')

    def build(self):
        ...

@ServiceClass
class SecurityService(Service, EncryptDecryptInterface):

    def __init__(self, configService: ConfigService, fileService: FileService) -> None:
        super().__init__()
        self.configService = configService

    def verify_server_access(self, token: str, sent_ip_addr) -> bool:
        token = self._decode_value(token, self.configService.API_ENCRYPT_TOKEN)
        token = token.split("|")
        # TODO invalidate with generation id

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