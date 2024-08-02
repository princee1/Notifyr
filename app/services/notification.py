from . import _service

## WARNING extends the ABC last

@_service.AbstractModuleClass
class BaseNotification(_service.Service): pass # BUG we can specify a kid class if we decide to inject a Notification

class SystemNotificationService(BaseNotification): pass

class DiscordService(BaseNotification): pass

