from abc import ABC
from module import Module

## WARNING extends the ABC last

class BaseNotification(Module,ABC): pass # BUG we can specify a kid class if we decide to inject a Notification

class SystemService(BaseNotification): pass

class DiscordService(BaseNotification): pass

