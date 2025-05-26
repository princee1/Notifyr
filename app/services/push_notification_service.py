
from .config_service import ConfigService
from app.definition._service import BaseService, Service, AbstractServiceClass
#import firebase_admin

@AbstractServiceClass
class PushNotificationService(BaseService):
    
    def __init__(self,configService:ConfigService):
        super().__init__()
        self.configService:ConfigService = configService

    def notify(self):
        ...


    

