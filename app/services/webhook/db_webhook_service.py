from typing import TypedDict
from httplib2 import Credentials
import psycopg2
import asyncpg
from pymongo import InsertOne, MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
from app.definition._error import BaseError
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, MiniService
from app.errors.service_error import BuildFailureError, BuildWarningError
from app.interface.webhook_adapter import WebhookAdapterInterface
from app.models.webhook_model import DBWebhookModel, MongoDBWebhookModel, PostgresWebhookModel
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.profile_service import ProfileMiniService
from app.utils.constant import StreamConstant
from pymongo.errors import ServerSelectionTimeoutError, ConfigurationError, OperationFailure

class DBPayload(TypedDict):
    mini_service_id: str
    data: dict

class WebhookBulkUploadError(BaseError):
    ...

class DBWebhookInterface(BaseMiniService,WebhookAdapterInterface):

    def __init__(self,scheme:str,depService:ProfileMiniService[DBWebhookModel],configService:ConfigService,redisService:RedisService):
        BaseMiniService.__init__(self,depService, None)
        WebhookAdapterInterface.__init__(self)
        self.scheme = scheme
        self.depService = depService
        self.configService = configService
        self.redisService = redisService

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
        payload:DBPayload = {
            "mini_service_id":self.miniService_id,
            "data":payload
        }
        resp = self.redisService.stream_data(StreamConstant.DB_WEBHOOK_STREAM,payload)
        return 201,resp
    
    async def deliver(self,payload):
        payload:DBPayload = {
            "mini_service_id":self.miniService_id,
            "data":payload
        }
        resp = await self.redisService.stream_data(StreamConstant.DB_WEBHOOK_STREAM,payload)
        return 201,resp
    
    async def bulk(self,payloads:list[dict]):
        ...

@MiniService()
class PostgresWebhookMiniService(DBWebhookInterface):

    def __init__(self, profileMiniService:ProfileMiniService[PostgresWebhookModel],configService:ConfigService,redisService:RedisService):
        super().__init__("postgresql",profileMiniService,configService,redisService)
        self.depService = profileMiniService

        try:
            self.conn = psycopg2.connect(dsn=self.url)
            return self.conn

        except psycopg2.OperationalError as e:
            # Network issues, authentication failure, DB not reachable, max connections
            raise BuildFailureError("OperationalError: Failed to connect to database:", e)

        except psycopg2.ProgrammingError as e:
            # Invalid DSN parameters or misuse
            raise BuildFailureError("ProgrammingError: Incorrect usage or parameters:", e)

        except psycopg2.DatabaseError as e:
            # Database-specific errors (e.g., SSL issues)
            raise BuildWarningError("DatabaseError: Database rejected the connection:", e)

    async def start(self):
        self.pool = await asyncpg.create_pool(dsn=self.url)

    async def close(self):
        await self.pool.close()

    async def bulk(self, payloads: list[tuple]):
        async with self.pool.acquire() as conn:
            await conn.executemany(
                f"INSERT INTO {self.model.table} (id, name) VALUES($1, $2)", payloads
            )

@MiniService()
class MongoDBWebhookMiniService(DBWebhookInterface):

    def __init__(self, profileMiniService:ProfileMiniService[MongoDBWebhookModel],configService:ConfigService,redisService:RedisService):
        super().__init__("mongodb",profileMiniService,configService,redisService)
        self.depService = profileMiniService
    
    def close(self):
        self.client.close()

    def build(self, build_state = ...):
       
        try:
            self.client = AsyncIOMotorClient(self.url, serverSelectionTimeoutMS=5000)
            client = MongoClient(self.url, serverSelectionTimeoutMS=5000)

            client[self.model.database][self.model.collection].find_one()
        except ServerSelectionTimeoutError:
            raise BuildFailureError("ServerSelectionTimeoutError: MongoDB server is unreachable.")
        except ConfigurationError:
            raise BuildFailureError("ConfigurationError: Invalid MongoDB configuration.")
        except OperationFailure:
            raise BuildFailureError("OperationFailure: Authentication failed or insufficient permissions.")

    async def bulk(self, payloads: list[dict]):
       operations = [InsertOne(payload) for payload in payloads]
       await self.client[self.model.database][self.model.collection].bulk_write(operations)   