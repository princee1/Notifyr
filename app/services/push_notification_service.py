
from services.config_service import ConfigService
from definition._service import Service, ServiceClass
import firebase_admin

@ServiceClass
class PushNotificationService(Service):
    
    def __init__(self,configService:ConfigService):
        super().__init__()
        self.configService:ConfigService = configService

    def notify(self):
        ...

    def build(self):
        return super().build()

    

