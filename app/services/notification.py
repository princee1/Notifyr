from . import _module

## WARNING extends the ABC last

@_module.AbstractModuleClass
class BaseNotification(_module.Module): pass # BUG we can specify a kid class if we decide to inject a Notification

class SystemNotificationService(BaseNotification): pass

class DiscordService(BaseNotification): pass

