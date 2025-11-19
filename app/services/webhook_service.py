from app.definition._service import BaseMiniService, BaseMiniServiceManager, BaseService, LinkDep, MiniServiceStore, Service, ServiceStatus
from app.interface.webhook_adapter import WebhookAdapterInterface
from app.models.webhook_model import WebhookProfileModel
from app.services.profile_service import ProfileService
from app.services.reactive_service import ReactiveService
from .config_service import ConfigService
from app.utils.helper import issubclass_of


@Service(
    links=[LinkDep(ProfileService,to_build=True,to_destroy=True)]
)
class WebhookService(BaseMiniServiceManager):
    
    def __init__(self,configService:ConfigService,profileService:ProfileService,reactiveService:ReactiveService):
        super().__init__()
        self.configService = configService
        self.profilesService = profileService
        self.reactiveService = reactiveService

        self.MiniServiceStore = MiniServiceStore[WebhookAdapterInterface|BaseMiniService](self.name)
    
    def build(self):
        count = self.profilesService.MiniServiceStore.filter_count(lambda p: issubclass_of(WebhookProfileModel,p.model.__class__)  )

    def close(self):
        ...
    
    async def start(self):
        ...

    