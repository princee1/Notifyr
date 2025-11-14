from app.services.push_notification_service import PushNotificationService
from app.container import InjectInMethod
from app.definition._ressource import BaseHTTPRessource, HTTPRessource

PUSH_NOTIFICATION_PREFIX = 'push-notification'

@HTTPRessource(PUSH_NOTIFICATION_PREFIX)
class PushNotificationRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,push_notificationService:PushNotificationService,):
        super().__init__()
        self.push_notificationService = push_notificationService
    