
from .config_service import ConfigService
from dataclasses import dataclass
from .file_service import FileService
from definition._service import Service, ServiceClass
import jwt

@ServiceClass
class SecurityService(Service):
    
    def __init__(self, configService: ConfigService, fileService: FileService) -> None:
        super().__init__()
        self.configService = configService

    def decode(self,):
        ...
    
    def _verify(self):
        ...

    def build(self):
        return super().build()

    def destroy(self):
        return super().destroy()
