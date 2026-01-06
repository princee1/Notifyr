from app.services.ntfr.notification_service import InAppNotificationService, PushNotificationService
from app.container import InjectInMethod
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, IncludeRessource

PUSH_NOTIFICATION_PREFIX = 'push'
IN_APP_NOTIFICATION_PREFIX = 'in-app'


@HTTPRessource(PUSH_NOTIFICATION_PREFIX)
class PushNotificationRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,push_notificationService:PushNotificationService,):
        super().__init__()
        self.push_notificationService = push_notificationService

@HTTPRessource(IN_APP_NOTIFICATION_PREFIX)
class InAppNotificationRessource(BaseHTTPRessource):
    
    @InjectInMethod()
    def __init__(self,inAppNotificationService:InAppNotificationService):
        super().__init__()
        self.inAppNotificationService = inAppNotificationService


@IncludeRessource(PushNotificationRessource)
@IncludeRessource(InAppNotificationRessource)
@HTTPRessource('notification')
class NotificationRessource(BaseHTTPRessource):
    
    @BaseHTTPRessource.HTTPRoute('/',[HTTPMethod.OPTIONS])
    def options(self):
        ...