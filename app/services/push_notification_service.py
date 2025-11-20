
from .config_service import ConfigService
from app.definition._service import BaseService, Service
#import firebase_admin

@Service()
class PushNotificationService(BaseService):
    
    def __init__(self,configService:ConfigService):
        super().__init__()
        self.configService:ConfigService = configService

    def notify(self):
        ...


    

