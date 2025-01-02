
from typing import Any
from .config_service import ConfigService
from dataclasses import dataclass
from .file_service import FileService
from definition._service import Service, ServiceClass
import jwt
from cryptography.fernet import Fernet
import base64
from fastapi import HTTPException,status
import time
from classes.permission import Permission

@ServiceClass
class JWTAuthService(Service):
    def __init__(self, configService: ConfigService, fileService: FileService) -> None:
        super().__init__()
        self.configService = configService
        self.fileService = fileService

    def _decode_value(self, value: str) -> Any:
        ...

    def _decode_token(self, token: str) -> dict:
        try:
            decoded = jwt.decode(token, self.configService, algorithms=self.configService.JWT_ALGORITHM)
            # TODO Check if the token is expired
            return decoded

        except jwt.InvalidSignatureError:
            ...
        except jwt.InvalidAlgorithmError as e:
            ...
        except jwt.InvalidKeyError as e:
            ...
        except jwt.ExpiredSignatureError  as e:
            ...
        except jwt.InvalidTokenError as e:
            ...
        except Exception as e:
            ...
        
        return

    def verify_permission(self, token: str, permission: Any) -> bool:
        # Decode the token if return None, trow an error
        ...

    def build(self):
        return super().build()

    def destroy(self):
        return super().destroy()

@ServiceClass
class SecurityService(Service):
    
    def __init__(self, configService: ConfigService, fileService: FileService) -> None:
        super().__init__()
        self.configService = configService

    def verify_server_access(self, token: str,sent_ip_addr) -> bool:
        # TODO The ip address of the client will be combined with the base api key a a random value and a creation time, to be hashed to create a special token
        cipher_suite = Fernet(self.configService.API_ENCRYPT_TOKEN)
        token = cipher_suite.decrypt(token.encode())
        token = str(base64.b64decode(token))
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

    def build(self):
        return super().build()

    def destroy(self):
        return super().destroy()
