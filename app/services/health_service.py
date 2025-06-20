
from app.definition._service import Service,ServiceClass
from app.services.task_service import BackgroundTaskService, CeleryService
from app.services.config_service import ConfigService

@ServiceClass
class HealthService(Service):
    
    def __init__(self,celeryService:CeleryService,backgroundService:BackgroundTaskService,configService:ConfigService):
        super().__init__()
        self.celeryService = celeryService
        self.backgroundService = backgroundService
        self.configService = configService
        
        

    def build(self):
        ...