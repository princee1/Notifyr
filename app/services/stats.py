from .notification import NotificationService
from .config import ConfigService
from definition import _service
from injector import inject


#@_service.InjectWithCondition(NotificationService,) BUG  added the metadata but its not in the dependency list 
class StatsService(_service.Service):
    def __init__(self,configService:ConfigService, notificationService:NotificationService) -> None:
        super().__init__()
        self.configService = configService
        self.notificationService = notificationService

    def notify(self):
        pass

    pass