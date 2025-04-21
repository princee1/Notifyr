from app.definition._service import Service, ServiceClass
from app.services.config_service import ConfigService


@ServiceClass
class LinkService(Service):
    
    def __init__(self,configService:ConfigService,):
        super().__init__()
        self.configService = configService
        self.base_url = self.configService

    
    def build(self):
        ...