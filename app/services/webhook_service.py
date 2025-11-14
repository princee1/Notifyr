from app.definition._service import BaseService, Service, ServiceStatus
from app.services.profile_service import ProfileService
from app.services.reactive_service import ReactiveService
from .config_service import ConfigService

@Service()
class WebhookService(BaseService):
    
    def __init__(self,configService:ConfigService,profileService:ProfileService,reactiveService:ReactiveService):
        super().__init__()
        self.configService = configService
        self.profileService = profileService
        self.reactiveService = reactiveService

    
    def build(self):
        ...