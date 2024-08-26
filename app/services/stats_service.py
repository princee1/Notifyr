from .notification_service import NotificationService
from .config_service import ConfigService
from definition import _service
from injector import inject


#@_service.InjectWithCondition(NotificationService,) BUG  added the metadata but its not in the dependency list 
@_service.ServiceClass
class StatsService(_service.Service):
    def __init__(self,configService:ConfigService, notificationService:NotificationService) -> None:
        super().__init__()
        self.configService = configService
        self.notificationService = notificationService

    def notify(self):
        pass

    pass