from urllib.parse import quote_plus
from app.definition._service import BaseMiniService
from app.interface.webhook_adapter import WebhookAdapterInterface
from app.models.webhook_model import MongoDBWebhookModel, PostgresWebhookModel
from app.services.database_service import RedisService
from app.services.profile_service import ProfileMiniService


class PostgresWebhookMiniService(BaseMiniService,WebhookAdapterInterface):

    def __init__(self, profileMiniService:ProfileMiniService[PostgresWebhookModel],redisService:RedisService):
        super().__init__(profileMiniService, None)
        self.depService = profileMiniService
        self.redisService = redisService
    
    @property
    def _uri(self) -> str:
        """
        Produce a full PostgreSQL URI (postgresql://…).
        Works whether the DB is supplied as an URL or host/port.
        """
        if self.from_url:
            return self.url

        auth = ""
        if self.auth:
            auth = f"{quote_plus(self.auth.username)}:{quote_plus(self.auth.password)}@"

        return f"postgresql://{auth}{self.host}:{self.port}"

class MongoDBWebhookMiniService(BaseMiniService,WebhookAdapterInterface):

    def __init__(self, profileMiniService:ProfileMiniService[MongoDBWebhookModel],redisService:RedisService):
        super().__init__(profileMiniService, None)
        self.depService = profileMiniService
        self.redisService = redisService
    
    @property
    def _uri(self) -> str:
        """
        Produce a MongoDB URI (mongodb://…).
        """
        if self.from_url:
            return self.url

        auth = ""
        if self.auth:
            auth = f"{quote_plus(self.auth.username)}:{quote_plus(self.auth.password)}@"

        return f"mongodb://{auth}{self.host}:{self.port}"