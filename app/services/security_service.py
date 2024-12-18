
from .config_service import ConfigService
from dataclasses import dataclass
from injector import inject
from .file_service import FileService
from definition._service import Service, ServiceClass


class KeyExchange:
    private_key: str
    public_key: str

    def __init__(self) -> None:
        pass


@ServiceClass
class SecurityService(Service):
    
    def __init__(self, configService: ConfigService, fileService: FileService) -> None:
        super().__init__()
        self.configService = configService

    def build(self):
        return super().build()

    def destroy(self):
        return super().destroy()
