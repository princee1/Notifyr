class BaseNotification: pass # BUG we can specify a kid class if we decide to inject a Notification

# class EmailNotificationService(BaseNotification): pass 

class SystemService(BaseNotification): pass

class DiscordService(BaseNotification): pass



