from classes.report import Report, SystemReport
from .config import ConfigService
from definition import _service

## WARNING extends the ABC last

ReportClass = {}

@_service.AbstractServiceClass
class NotificationService(_service.Service): 
    def __init__(self,configService: ConfigService) -> None:
        super().__init__()
        self.configService = ConfigService
    
    def notify(self,):

        self.treatArgument()
        self.__notify()
        pass
    
    def treatArgument(self, *args):
        pass

    def __notify(self, report:Report):
        pass
    pass # BUG we can specify a kid class if we decide to inject a Notification

class SystemNotificationService(NotificationService): pass

class DiscordService(NotificationService): pass

class EmailNotificationService(NotificationService):pass

class AYCDNotificationService(NotificationService): pass

class GoogleNotificationService(NotificationService): pass


