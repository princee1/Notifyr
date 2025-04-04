from app.services.celery_service import CeleryService,BackgroundTaskService,OffloadTaskService
from app.container import Register

Register(BackgroundTaskService)
Register(CeleryService)
Register(OffloadTaskService)


from .support_ressource import *
from .email_ressource import *
from .sms_ressource import *
from .fax_ressource import *
from .voice_ressource import *
from .support_ressource import *
from .admin_ressource import AdminRessource
from .redis_backend_ressource import *
from .contacts_ressources import ContactsRessource
from .auth_ressource import AuthRessource
