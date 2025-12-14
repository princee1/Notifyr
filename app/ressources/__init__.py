from typing import Type
from app.services.celery_service import CeleryService
from app.services.config_service import AssetMode, ConfigService
from app.container import Register, Get
from app.services.workflow_service import WorkflowService

Register(CeleryService)
Register(WorkflowService)

configService = Get(ConfigService)

from .support_ressource import SupportRessource
from .email_ressource import EmailRessource
from .admin_ressource import AdminRessource
from .result_ressource import ResultBackendRessource
from .contacts_ressources import ContactsRessource
from .auth_ressource import AuthRessource
from .twilio_ressource import TwilioRessource
from .app_ressource import AppRessource
from .link_ressource import LinkRessource
from .ping_pong_ressource import PingPongRessource
from .properties_ressource import PropertiesRessource
from .analytics_ressource import AnalyticsRessource
from .profile_ressource import ProfilRessource
from .object_s3_ressource import S3ObjectRessource
from .cost_ressource import CostRessource
from .celery_ressource import CeleryRessource
from app.definition._ressource import BaseHTTPRessource

#from .notification_ressource import NotificationRessource

BASE_RESSOURCES:list[Type[BaseHTTPRessource]] = [SupportRessource,
                                                 EmailRessource,
                                                 AdminRessource,
                                                 ResultBackendRessource,
                                                 ContactsRessource,
                                                 AuthRessource,
                                                 TwilioRessource,
                                                 AppRessource,
                                                 LinkRessource,
                                                 PingPongRessource,
                                                 PropertiesRessource,
                                                 AnalyticsRessource,
                                                 ProfilRessource,
                                                 CostRessource,
                                                 CeleryRessource
                                                 #PushNotificationRessource,
]
if configService.ASSET_MODE == AssetMode.s3:
    BASE_RESSOURCES.append(S3ObjectRessource)
