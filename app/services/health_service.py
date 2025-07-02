from app.definition._service import InjectWithCondition, Service,BaseService
#from app.services.celery_service import CeleryService, TaskService
from app.services.config_service import ConfigService
from app.services.notification_service import DiscordService, NotificationService,SystemNotificationService

def resolve_notification_service(configService:ConfigService):
    return DiscordService if True else SystemNotificationService

@Service
#@InjectWithCondition(NotificationService,resolve_notification_service)
class HealthService(BaseService):
    
    def __init__(self,configService:ConfigService,discordService:DiscordService):
        super().__init__()
        self.configService = configService
        self.notificationService = discordService

    def build(self):
        ...