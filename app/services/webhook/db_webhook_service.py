from httplib2 import Credentials
import psycopg2
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService
from app.interface.webhook_adapter import WebhookAdapterInterface
from app.models.webhook_model import DBWebhookModel, MongoDBWebhookModel, PostgresWebhookModel
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.profile_service import ProfileMiniService


class DBInterface(BaseMiniService,WebhookAdapterInterface):

    def __init__(self,scheme:str,topic:str, depService:ProfileMiniService[DBWebhookModel],configService:ConfigService,redisService:RedisService):
        BaseMiniService.__init__(self,depService, None)
        WebhookAdapterInterface.__init__(self)
        self.scheme = scheme
        self.depService = depService
        self.configService = configService
        self.redisService = redisService
        self.topic=topic

    @property
    def model(self):
        return self.depService.model
    
    @property
    def url(self) -> str:
        """
        Produce a full DB URI (postgresql://… or mongodb://...).
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
        
        return f"{self.scheme}://{auth}{self.model.host}:{self.model.port}/{self.model.database}"

    def deliver(self,payload):
        resp = self.redisService.stream_data(self.topic,payload)
        return 201,resp
    
    async def deliver(self,payload):
        resp = await self.redisService.stream_data(self.topic,payload)
        return 201,resp
    
    async def bulk(self,payloads:list[dict]):
        ...

class PostgresWebhookMiniService(DBInterface):

    def __init__(self, profileMiniService:ProfileMiniService[PostgresWebhookModel],configService:ConfigService,redisService:RedisService):
        super().__init__("postgresql","",profileMiniService,configService,redisService)
        self.depService = profileMiniService

    def build(self, build_state = DEFAULT_BUILD_STATE):
        try:
            self.conn_async = psycopg2.connect(async_=True,dsn=self.url)
            self.conn = psycopg2.connect(dsn=self.url)
        except:
            ...
        
    def close(self):
        self.conn.close()
        self.conn_async.close()

class MongoDBWebhookMiniService(DBInterface):

    def __init__(self, profileMiniService:ProfileMiniService[MongoDBWebhookModel],configService:ConfigService,redisService:RedisService):
        super().__init__("mongodb","",profileMiniService,configService,redisService)
        self.depService = profileMiniService
    
    def close(self):
        self.client_async.close()
        self.client.close()

    def build(self, build_state = ...):
        try:
            self.client_async = AsyncIOMotorClient(self.url)
            self.client = MongoClient(self.url)
        except:
            ...

