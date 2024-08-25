
from injector import inject
from .config import ConfigService
from definition._service import Service,ServiceClass

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

