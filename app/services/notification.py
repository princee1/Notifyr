from abc import ABC
from . import _module

## WARNING extends the ABC last

class BaseNotification(_module.Module,ABC): pass # BUG we can specify a kid class if we decide to inject a Notification

class SystemNotificationService(BaseNotification): pass

class DiscordService(BaseNotification): pass

