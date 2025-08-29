from app.services.task_service import CeleryService,TaskService,OffloadTaskService
from app.container import Register

Register(CeleryService)
Register(TaskService)
Register(OffloadTaskService)


from .support_ressource import SupportRessource
from .email_ressource import EmailTemplateRessource
from .admin_ressource import AdminRessource
from .redis_backend_ressource import RedisResultBackendRessource
from .contacts_ressources import ContactsRessource
from .auth_ressource import AuthRessource
from .twilio_ressource import TwilioRessource
from .app_ressource import AppRessource
from .link_ressource import LinkRessource
from .ping_pong_ressource import PingPongRessource
from .properties_ressource import PropertiesRessource
from .analytics_ressource import AnalyticsRessource
#from .profile_ressource import ProfileRessource
#from .push_notification_ressource import PushNotificationRessource

BASE_RESSOURCES = [SupportRessource,EmailTemplateRessource,AdminRessource,RedisResultBackendRessource,ContactsRessource,AuthRessource,TwilioRessource,AppRessource,LinkRessource,PingPongRessource,PropertiesRessource,AnalyticsRessource]