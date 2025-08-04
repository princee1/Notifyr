from app.services.task_service import CeleryService,TaskService,OffloadTaskService
from app.container import Register

Register(CeleryService)
Register(TaskService)
Register(OffloadTaskService)


from .support_ressource import *
from .email_ressource import *
from .admin_ressource import AdminRessource
from .redis_backend_ressource import *
from .contacts_ressources import ContactsRessource
from .auth_ressource import AuthRessource
from .twilio_ressource import TwilioRessource
from .app_ressource import AppRessource
from .link_ressource import LinkRessource
from .ping_pong_ressource import PingPongRessource
from .globals_variable_ressource import GlobalAssetVariableRessource