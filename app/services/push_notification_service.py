
from .config_service import ConfigService
from app.definition._service import Service, ServiceClass
import firebase_admin

@ServiceClass
class PushNotificationService(Service):
    
    def __init__(self,configService:ConfigService):
        super().__init__()
        self.configService:ConfigService = configService

    def notify(self):
        ...


    

