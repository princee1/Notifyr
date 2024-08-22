from .notification import NotificationService
from .config import ConfigService
from interface import _service
from injector import inject

class StatsService(_service.Service):
    def __init__(self,configService:ConfigService, notificationService:NotificationService) -> None:
        super().__init__()
        self.configService = configService
        self.notificationService = notificationService

    def notify(self):
        pass

    pass