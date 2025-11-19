from urllib.parse import quote_plus

from httplib2 import Credentials
from app.definition._service import BaseMiniService
from app.interface.webhook_adapter import WebhookAdapterInterface
from app.models.webhook_model import DBWebhookModel, MongoDBWebhookModel, PostgresWebhookModel
from app.services.database_service import RedisService
from app.services.profile_service import ProfileMiniService


class DBInterface(BaseMiniService,WebhookAdapterInterface):

    def __init__(self,scheme:str, depService:ProfileMiniService[DBWebhookModel]):
        super().__init__(depService, None)
        self.scheme = scheme
        self.depService = depService

    @property
    def model(self):
        return self.depService.model
    
    @property
    def url(self) -> str:
        """
        Produce a full PostgreSQL URI (postgresql://…).
        Works whether the DB is supplied as an URL or host/port.
        """
        creds:Credentials = self.depService.credentials
        if self.model.from_url:
            return creds['url']

        auth=""
        if 'auth' in creds:
            username = creds['username']
            password = creds['password']
            auth = f"{username}:{password}@"
        
        return f"{self.scheme}://{auth}{self.model.host}:{self.model.port}"
    

class PostgresWebhookMiniService(DBInterface):

    def __init__(self, profileMiniService:ProfileMiniService[PostgresWebhookModel],redisService:RedisService):
        super().__init__("postgresql",profileMiniService)
        self.depService = profileMiniService
        self.redisService = redisService


class MongoDBWebhookMiniService(BaseMiniService,WebhookAdapterInterface):

    def __init__(self, profileMiniService:ProfileMiniService[MongoDBWebhookModel],redisService:RedisService):
        super().__init__("mongodb",profileMiniService)
        self.depService = profileMiniService
        self.redisService = redisService
    
    