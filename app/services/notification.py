from interface import _service

## WARNING extends the ABC last

@_service.AbstractServiceClass
class Notification(_service.Service): 
    def __init__(self) -> None:
        super().__init__()
    
    pass # BUG we can specify a kid class if we decide to inject a Notification

class SystemNotificationService(Notification): pass

class DiscordService(Notification): pass

class EmailNotificationService(Notification):pass

class AYCDNotificationService(Notification): pass

class GoogleNotificationService(Notification): pass

