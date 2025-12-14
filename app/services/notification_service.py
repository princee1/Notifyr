from app.services.link_service import LinkService
from .config_service import ConfigService
from app.definition._service import BaseService, Service
#import firebase_admin

@Service()
class PushNotificationService(BaseService):
    
    def __init__(self,configService:ConfigService,linkService:LinkService):
        super().__init__()
        self.configService:ConfigService = configService
        self.linkService = linkService

    def notify(self):
        ...

@Service()
class InAppNotificationService(BaseService):

    def __init__(self,configService:ConfigService,linkService:LinkService):
        super().__init__()
        self.configService = configService
        self.linkService = linkService
    

