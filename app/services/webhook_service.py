from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, BaseMiniServiceManager, BaseService, LinkDep, MiniServiceStore, Service, ServiceStatus
from app.interface.webhook_adapter import WebhookAdapterInterface
from app.models.webhook_model import DiscordWebhookModel, HTTPWebhookModel, KafkaWebhookModel, MongoDBWebhookModel, N8nHTTPWebhookModel, PostgresWebhookModel, RedisWebhookModel, SQSWebhookModel, SlackHTTPWebhookModel, WebhookProfileModel, ZapierHTTPWebhookModel
from app.services.database_service import RedisService
from app.services.profile_service import ProfileService
from app.services.reactive_service import ReactiveService
from app.services.webhook.broker_webhook_service import KafkaWebhookMiniService, RedisWebhookMiniService, SQSWebhookMiniService
from app.services.webhook.db_webhook_service import MongoDBWebhookMiniService, PostgresWebhookMiniService
from app.services.webhook.http_webhook_service import HTTPWebhookMiniService
from app.services.webhook.provider_webhook_service import DiscordWebhookMiniService, MakeWebhookMiniService, MakeWebhookMiniService, N8NWebhookMiniService, SlackIncomingWebhookMiniService, ZapierWebhookMiniService
from .config_service import ConfigService
from app.utils.helper import issubclass_of


@Service(
    links=[LinkDep(ProfileService,to_build=True,to_destroy=True)]
)
class WebhookService(BaseMiniServiceManager):

    model_class_to_service = {
        RedisWebhookModel: RedisWebhookMiniService,
        HTTPWebhookModel: HTTPWebhookMiniService,
        KafkaWebhookModel: KafkaWebhookMiniService,
        SQSWebhookModel: SQSWebhookMiniService,
        DiscordWebhookModel: DiscordWebhookMiniService,
        SlackHTTPWebhookModel: SlackIncomingWebhookMiniService,
        ZapierHTTPWebhookModel: ZapierWebhookMiniService,
        KafkaWebhookModel: MakeWebhookMiniService,
        N8nHTTPWebhookModel: N8NWebhookMiniService,
        PostgresWebhookModel: PostgresWebhookMiniService,
        MongoDBWebhookModel: MongoDBWebhookMiniService,

        
    }
    
    def __init__(self,configService:ConfigService,profileService:ProfileService,reactiveService:ReactiveService,redisService:RedisService):
        super().__init__()
        self.configService = configService
        self.profilesService = profileService
        self.reactiveService = reactiveService
        self.redisService = redisService

        self.MiniServiceStore = MiniServiceStore[WebhookAdapterInterface|BaseMiniService](self.name)

    def build(self,build_state=DEFAULT_BUILD_STATE):
        count = self.profilesService.MiniServiceStore.filter_count(lambda p: issubclass_of(WebhookProfileModel,p.model.__class__)  )
        state_counter = self.StatusCounter(count)

        for i,profile in self.profilesService.MiniServiceStore:
            model = profile.model.__class__
            cls = self.model_class_to_service.get(model,None)
            if cls is None:
                continue

            miniService:BaseMiniService|WebhookAdapterInterface = cls(profile,self.configService,self.redisService)
            miniService._builder(BaseMiniService.QUIET_MINI_SERVICE,build_state,self.CONTAINER_LIFECYCLE_SCOPE)

            state_counter.count(miniService)
            self.MiniServiceStore.add(miniService)

        super().build(state_counter)

    def close(self):
        ...
    
    async def start(self):
        ...

    