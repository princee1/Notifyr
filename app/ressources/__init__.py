from typing import Type
from app.services.config_service import AssetMode, ConfigService
from app.services.task_service import CeleryService,TaskService,OffloadTaskService
from app.container import Register, Get
from app.services.workflow_service import WorkflowService

Register(CeleryService)
Register(TaskService)
Register(OffloadTaskService)
Register(WorkflowService)


configService = Get(ConfigService)

from .support_ressource import SupportRessource
from .email_ressource import EmailRessource
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
from .profile_ressource import ProfilRessource
from .object_s3_ressource import S3ObjectRessource
from .cost_ressource import CostRessource
from app.definition._ressource import BaseHTTPRessource

#from .push_notification_ressource import PushNotificationRessource

BASE_RESSOURCES:list[Type[BaseHTTPRessource]] = [SupportRessource,
                                                 EmailRessource,
                                                 AdminRessource,
                                                 RedisResultBackendRessource,
                                                 ContactsRessource,
                                                 AuthRessource,
                                                 TwilioRessource,
                                                 AppRessource,
                                                 LinkRessource,
                                                 PingPongRessource,
                                                 PropertiesRessource,
                                                 AnalyticsRessource,
                                                 ProfilRessource,
                                                 CostRessource
                                                 #PushNotificationRessource,
]
if configService.ASSET_MODE == AssetMode.s3:
    BASE_RESSOURCES.append(S3ObjectRessource)
