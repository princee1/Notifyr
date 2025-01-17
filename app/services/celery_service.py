from app.services.config_service import ConfigService
from definition._service import Service, ServiceClass

@ServiceClass
class CeleryService(ServiceClass):
    
    def __init__(self,configService:ConfigService):
        self.configService = configService
    
    