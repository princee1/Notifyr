from app.services.push_notification_service import PushNotificationService
from app.container import InjectInMethod
from app.definition._ressource import BaseRessource, Ressource

PUSH_NOTIFICATION_PREFIX = 'push-notification'

@Ressource(PUSH_NOTIFICATION_PREFIX)
class PushNotificationRessource(BaseRessource):

    @InjectInMethod
    def __init__(self,push_notificationService:PushNotificationService,):
        super().__init__()
        self.push_notificationService = push_notificationService
    