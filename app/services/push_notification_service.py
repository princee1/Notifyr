
from .config_service import ConfigService
from app.definition._service import Service, ServiceClass, AbstractServiceClass
#import firebase_admin

@AbstractServiceClass
class PushNotificationService(Service):
    
    def __init__(self,configService:ConfigService):
        super().__init__()
        self.configService:ConfigService = configService

    def notify(self):
        ...


    

