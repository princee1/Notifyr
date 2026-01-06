from typing import Type
from app.services.worker.celery_service import CeleryService
from app.services.config_service import AssetMode, ConfigService
from app.services import CostService
from app.container import Register, Get
from app.utils.globals import CAPABILITIES

Register(CeleryService)

configService = Get(ConfigService)
costService = Get(CostService)

from .support_ressource import SupportRessource
from .admin_ressource import AdminRessource
from .result_ressource import ResultBackendRessource
from .contacts_ressources import ContactsRessource
from .auth_ressource import AuthRessource
from .app_ressource import AppRessource
from .link_ressource import LinkRessource
from .ping_pong_ressource import PingPongRessource
from .properties_ressource import PropertiesRessource
from .analytics_ressource import AnalyticsRessource
from .profile_ressource import ProfilRessource
from .cost_ressource import CostRessource
from .celery_ressource import CeleryRessource
from app.definition._ressource import BaseHTTPRessource


BASE_RESSOURCES:list[Type[BaseHTTPRessource]] = [SupportRessource,
                                                 AdminRessource,
                                                 ResultBackendRessource,
                                                 ContactsRessource,
                                                 AuthRessource,
                                                 AppRessource,
                                                 LinkRessource,
                                                 PingPongRessource,
                                                 PropertiesRessource,
                                                 AnalyticsRessource,
                                                 ProfilRessource,
                                                 CostRessource,
                                                 CeleryRessource]


if CAPABILITIES['object']:
    from .object_s3_ressource import S3ObjectRessource
    from .blog_ressource import BlogsRessource
    if configService.ASSET_MODE == AssetMode.s3:
        BASE_RESSOURCES.append(S3ObjectRessource)
    BASE_RESSOURCES.append(BlogsRessource)
    

if CAPABILITIES['webhook']:
    ...

if CAPABILITIES['workflow']:
    ...

if CAPABILITIES['twilio']:
    from .twilio_ressource import TwilioRessource
    BASE_RESSOURCES.append(TwilioRessource)

if CAPABILITIES['email']:
    from .email_ressource import EmailRessource
    BASE_RESSOURCES.append(EmailRessource)

if CAPABILITIES['agentic']:
    from app.ressources.rag_db_ressource import RagDBRessource
    from app.ressources.agent_ressource import AgentsRessource
    BASE_RESSOURCES.append(RagDBRessource)
    BASE_RESSOURCES.append(AgentsRessource)


if CAPABILITIES['notification']:
    from .notification_ressource import NotificationRessource
    BASE_RESSOURCES.append(NotificationRessource)

if CAPABILITIES['message']:
    ...
