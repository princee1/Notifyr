
from dataclasses import dataclass
from injector import inject
from .config_service import ConfigService
from definition._service import Service,ServiceClass

class KeyExchange:
    private_key:str
    public_key:str

    def __init__(self) -> None:
        pass


@ServiceClass
class SecurityService(Service):
    @inject
    def __init__(self, configService: ConfigService) -> None:
        super().__init__()
        self.configService = configService

    def build(self):
        return super().build()
    
    def destroy(self):
        return super().destroy()

