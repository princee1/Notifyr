
from injector import inject
from .config import ConfigService
from ._service import Service
class SecurityService(Service):
    @inject
    def __init__(self, configService: ConfigService) -> None:
        super().__init__()
        self.configService = configService

    def build(self):
        return super().build()
    
    def destroy(self):
        return super().destroy()

