from .notification_service import DiscordService, NotificationService
from .config_service import ConfigService
from app.definition import _service
from injector import inject

class Stats:
    ...


# @_service.InjectWithCondition(NotificationService,resolvedClass=DiscordService) BUG  added the metadata but its not in the dependency list 
class StatsService(_service.Service):
    def __init__(self,configService:ConfigService, notificationService:NotificationService) -> None:
        super().__init__()
        self.configService = configService
        self.notificationService = notificationService

    def notify(self):
        pass    