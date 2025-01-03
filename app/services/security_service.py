
from typing import Any, Dict

from definition._interface import Interface, IsInterface
from .config_service import ConfigService
from dataclasses import dataclass
from .file_service import FileService
from definition._service import AbstractServiceClass, Service, ServiceClass
import jwt
from cryptography.fernet import Fernet
import base64
from fastapi import HTTPException, status
import time
from classes.permission import PermissionAuth, RoutePermission
from random import randint


SEPARATOR = "|"


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

    def encode_auth_token(self, data: Dict[str, RoutePermission], issue_for: str) -> str:
        try:
            permission = PermissionAuth(issued_for=issue_for, created_at=time.time(
            ), expired_at=time.time() + self.configService.AUTH_EXPIRATION, allowed_routes=data)
            encoded = jwt.encode(permission, self.configService.JWT_SECRET_KEY,
                                 algorithm=self.configService.JWT_ALGORITHM)
            return self._encode_value(encoded, self.configService.ON_TOP_SECRET_KEY)
        except Exception as e:
            print(e)
        return

    def _decode_auth_token(self, token: str) -> dict:
        try:
            token = self._decode_value(
                token, self.configService.ON_TOP_SECRET_KEY)
            decoded = jwt.decode(token, self.configService,
                                 algorithms=self.configService.JWT_ALGORITHM)
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

    def verify_permission(self, token: str, class_name: str, func_name: str, issued_for: str) -> bool:

        token = self._decode_auth_token(token)
        permission = PermissionAuth(**token)

        if issued_for != permission.issued_for:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Token not issued for this user")

        if permission.expired_at < time.time():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,  detail="Token expired")

        if class_name not in permission.allowed_routes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Ressource not allowed")

        routePermission:RoutePermission = permission.allowed_routes[class_name]
        if routePermission["scope"] == "all":
            return True

        if func_name not in permission.allowed_routes[class_name]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Route not allowed")

        return True


@ServiceClass
class SecurityService(Service, EncryptDecryptInterface):

    def __init__(self, configService: ConfigService, fileService: FileService) -> None:
        super().__init__()
        self.configService = configService

    def verify_server_access(self, token: str, sent_ip_addr) -> bool:
        token = self._decode_value(token, self.configService.API_ENCRYPT_TOKEN)
        token = token.split("|")
        if len(token) != 4:
            return False
        ip_addr = token[0]

        if ip_addr != sent_ip_addr:
            return False

        if time.time() - token[2] > self.configService.API_EXPIRATION:
            return False

        if token[3] != self.configService.API_KEY:
            return False

        return True

    def generate_custom_api_key(self, ip_address: str):
        data = ip_address + SEPARATOR + SEPARATOR + \
            str(time.time_ns()) + SEPARATOR + self.configService.API_KEY
        return self._encode_value(data, self.configService.API_ENCRYPT_TOKEN)
