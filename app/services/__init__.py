from app.utils.globals import APP_MODE,ApplicationMode,CAPABILITIES

from app.services.config_service import ConfigService,UvicornWorkerService
from app.services.logger_service import LoggerService


if APP_MODE == ApplicationMode.beat or APP_MODE == ApplicationMode.server or APP_MODE == ApplicationMode.worker:
    from app.services.vault_service import VaultService
    from app.services.database.redis_service import RedisService

if APP_MODE == ApplicationMode.worker or APP_MODE == ApplicationMode.server:
    from app.services.vault_service import VaultService
    from app.services.database.mongoose_service import MongooseService
    from app.services.profile_service import ProfileService
    from app.services.cost_service import CostService
    from app.services.monitoring_service import MonitoringService
    from app.services.database.rabbitmq_service import RabbitMQService
    
    from app.services.workflow_service import WorkflowService
    from app.services.webhook_service import WebhookService
    from app.services.agent.remote_agent_service import RemoteAgentService

    if CAPABILITIES['twilio']:
        from app.services.twilio_service import TwilioService,CallService,SMSService
    
    if CAPABILITIES['email']:
        from app.services.email_service import EmailReaderService,EmailSenderService
    
    if CAPABILITIES['message']:
        ...
    
    if CAPABILITIES['notification']:
        from app.services.push_notification_service import PushNotificationService
    
if APP_MODE == ApplicationMode.server:
    if CAPABILITIES['object']:
        from app.services.assets_service import AssetService
        from app.services.object_service import ObjectS3Service

    from app.services.chat_service import ChatService
    from app.services.database.memcached_service import  MemCachedService
    from app.services.database.tortoise_service import TortoiseConnectionService
    from app.services.link_service import LinkService
    from app.services.admin_service import AdminService
    from app.services.reactive_service import ReactiveService
    from app.services.health_service import HealthService
    from app.services.task_service import TaskService
    from app.services.setting_service import SettingService
    from app.services.security_service import JWTAuthService,SecurityService
    from app.services.file.file_service import FileService
    from app.services.contacts_service import ContactsService,SubscriptionService
    from app.services.worker.arq_service import ArqDataTaskService


if APP_MODE == ApplicationMode.agentic and CAPABILITIES['agentic']:
    from app.services.database.redis_service import RedisService
    from app.services.cost_service import CostService
    from app.services.monitoring_service import MonitoringService
    from app.services.database.memcached_service import MemCachedService
    from app.services.vault_service import VaultService
    from app.services.database.mongoose_service import MongooseService
    from app.services.agent.llm_provider_service import LLMProviderService
    from app.services.agent.remote_agent_service import RemoteAgentService
    from app.services.agent.agent_service import AgentService
    from app.services.database.qdrant_service import QdrantService
    from app.services.database.neo4j_service import Neo4JService
    from app.services.file.file_service import FileService
    from app.services.profile_service import ProfileService


if APP_MODE == ApplicationMode.arq:
    from app.services.vault_service import VaultService
    from app.services.database.mongoose_service import MongooseService
    from app.services.agent.llm_provider_service import LLMProviderService
    from app.services.database.qdrant_service import QdrantService
    from app.services.database.neo4j_service import Neo4JService
    from app.services.database.redis_service import RedisService
    from app.services.file.file_service import FileService
    from app.services.worker.arq_service import ArqDataTaskService


if APP_MODE == ApplicationMode.gunicorn and CAPABILITIES['object']:
    from app.services.file.file_service import FileService
    from app.services.file.file_fetcher_service import GitCloneRepoService,FTPService
    from app.services.vault_service import VaultService
    from app.services.object_service import ObjectS3Service
    from app.services.assets_service import AssetService

    
