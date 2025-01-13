from services.push_notification_service import PushNotificationService
from container import InjectInMethod
from definition._ressource import BaseRessource, Ressource

PUSH_NOTIFICATION_PREFIX = 'push-notification'

@Ressource(PUSH_NOTIFICATION_PREFIX)
class PushNotificationRessource(BaseRessource):

    @InjectInMethod
    def __init__(self,push_notificationService:PushNotificationService,):
        super().__init__()
        self.push_notificationService = push_notificationService
    