from app.definition._service import Service, ServiceClass, ServiceStatus
from .config_service import ConfigService

@ServiceClass
class WebhookService(Service):
    
    def __init__(self,configService:ConfigService):
        super().__init__()

        self.configService = configService

    
    def build(self):
        ...