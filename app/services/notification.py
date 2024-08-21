from interface import _service

## WARNING extends the ABC last

@_service.AbstractServiceClass
class BaseNotification(_service.Service): 
    def __init__(self) -> None:
        super().__init__()
    
    pass # BUG we can specify a kid class if we decide to inject a Notification

class SystemNotificationService(BaseNotification): pass

class DiscordService(BaseNotification): pass

