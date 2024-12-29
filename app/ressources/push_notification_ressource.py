from services.push_notification_service import PushNotificationService
from container import InjectInMethod
from definition._ressource import Ressource

PUSH_NOTIFICATION_PREFIX = 'push-notification'
class PushNotificationRessource(Ressource):

    @InjectInMethod
    def __init__(self,push_notificationService:PushNotificationService,):
        super().__init__(PUSH_NOTIFICATION_PREFIX)
    