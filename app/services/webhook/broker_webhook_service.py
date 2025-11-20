import json
from typing import Any
from aiokafka import AIOKafkaProducer, abc
import aiobotocore as aiobotocore_session
import boto3
from confluent_kafka import Producer as SyncKafkaProducer
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService
from app.interface.webhook_adapter import WebhookAdapterInterface
from app.models.webhook_model import AuthConfig, KafkaWebhookModel, RedisWebhookModel, SQSWebhookModel
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.profile_service import ProfileMiniService
from redis.asyncio import Redis,from_url as async_from_url
from redis import Redis as SyncRedis,from_url

# ---------- KafkaAdapter (aiokafka + optional sync kafka-python) ----------
class KafkaWebhookMiniService(BaseMiniService,WebhookAdapterInterface):

    def __init__(self,profileMiniService:ProfileMiniService[KafkaWebhookModel],configService:ConfigService,redisService:RedisService):
        super().__init__(profileMiniService,None)
        WebhookAdapterInterface.__init__(self)
        self.redisService = redisService
        self.configService = configService
        self.depService = profileMiniService
        self._started = False
        self._started_sync = False
        self.producer = None
        self.producer_sync = None
    
    @property
    def model(self):
        return self.depService.model

    def build(self,build_state=DEFAULT_BUILD_STATE):

        bootstrap_servers  = self.model.bootstrap_servers
        creds = self.depService.credentials.to_plain()
        auth:AuthConfig = creds.get('auth',{})
        client_id = self.model.client_id
        global_kwargs = {
            "bootstrap_servers": bootstrap_servers,
            "client_id": client_id,
            "acks": self.model.acks,
        }
        global_kwargs["compression_type"] = self.model.compression
        if auth:
            global_kwargs["sasl_plain_username"] = auth.get("username")
            global_kwargs["sasl_plain_password"] = auth.get("password")

        async_kwargs = dict(global_kwargs)
        async_kwargs["enable_idempotence"] = self.model.enable_idempotence

        # create async producer
        self.producer = AIOKafkaProducer(**async_kwargs)
        self.producer_sync = SyncKafkaProducer(**global_kwargs)
        self._started_sync = True

    async def start(self):
        if not self._started:
            await self.producer.start()
            self._started = True

    async def stop(self):
        if self._started:
            await self.producer.stop()
            self._started = False
    

    def prepare_request(self, payload):
        topic = self.model.topic
        key = self.model.key or self.generate_delivery_id()
        payload_bytes = self.json_bytes(payload)
        key_bytes = str(key).encode("utf-8")
        return topic,payload_bytes,key_bytes

    @WebhookAdapterInterface.retry
    def deliver(self,payload: Any):
        topic, payload_bytes, key_bytes = self.prepare_request(payload)
        self.producer_sync.send(topic, value=payload_bytes, key=key_bytes)
        return 200, b"OK"
    
    @WebhookAdapterInterface.batch
    @WebhookAdapterInterface.retry
    async def deliver_async(self,payload: Any):
        topic, payload_bytes, key_bytes = self.prepare_request(payload)
        if self.model.send_and_wait:
            await self.producer.send_and_wait(topic, payload_bytes, key=key_bytes)
        else:
            await self.producer.send(topic, payload_bytes, key=key_bytes)
        return 200, b"OK"

# ---------- SQSAdapter (aiobotocore + boto3 sync) ----------
class SQSWebhookMiniService(BaseMiniService,WebhookAdapterInterface):

    def __init__(self,profileMiniService:ProfileMiniService[SQSWebhookModel],configService:ConfigService,redisService:RedisService):
        super().__init__(profileMiniService, None)
        WebhookAdapterInterface.__init__(self)

        self.redisService = redisService
        self.configService= configService
        self.depService = profileMiniService
        self.client = None
        self.client_sync = None

    @property
    def model(self):
        return self.depService.model

    def build(self,build_state=DEFAULT_BUILD_STATE):
        self._session = aiobotocore_session.get_session()
        creds = self.depService.credentials.to_plain()
        self.client = self._session.create_client(
            "sqs",
            region_name=self.model.region,
            aws_secret_access_key=creds.get('aws_secret_access_key'),
            aws_access_key_id=creds.get('aws_access_key_id')
        )
        self.client_sync = boto3.client(
                "sqs",
                region_name=self.model.region,
                aws_secret_access_key=creds.get('aws_secret_access_key'),
                aws_access_key_id=creds.get('aws_access_key_id')
            )
        
    @WebhookAdapterInterface.retry
    def deliver(self, payload: Any):
        kwargs = self.prepare_request(payload)
        resp = self.client_sync.send_message(**kwargs)
        return 200, json.dumps(resp).encode("utf-8")

    @WebhookAdapterInterface.batch
    @WebhookAdapterInterface.retry
    async def deliver_async(self, payload: Any):
        kwargs = self.prepare_request(payload)
        resp = await self.client.send_message(**kwargs)
        return 200, json.dumps(resp).encode("utf-8")

    def prepare_request(self, payload):
        delivery_id = self.generate_delivery_id()
        body = json.dumps(payload)
        kwargs = {"QueueUrl": self.model.url, "MessageBody": body}
        if self.model.message_group_id_template:
            kwargs["MessageGroupId"] = self.model.message_group_id_template
            kwargs["MessageDeduplicationId"] = self.model.message_group_id_template or delivery_id
        return kwargs


# ---------- RedisAdapter (streams, lists, pubsub) ----------
class RedisWebhookMiniService(BaseMiniService,WebhookAdapterInterface):

    def __init__(self,profileMiniService:ProfileMiniService[RedisWebhookModel],configService:ConfigService,redisService:RedisService):
        super().__init__(profileMiniService, None)
        WebhookAdapterInterface.__init__(self)

        self.depService = profileMiniService
        self.configService = configService
        self.redisService = redisService
        

    @property
    def model(self):
        return self.depService.model

    def build(self,build_state= DEFAULT_BUILD_STATE):
        creds = self.depService.credentials.to_plain()
        auth:AuthConfig = creds.get('auth',{})
        username = auth.get('username',None)
        password = auth.get('password',None)
        if self.model.from_url:
            self.sync_conn = from_url(self.model.url)
            self.conn = async_from_url(self.model.url)
        else:
            self.sync_conn = SyncRedis(
                host=self.model.url,
                port=self.model.port,
                username=username,
                password=password
            )
            self.conn= Redis(
                host=self.model.url,
                port=self.model.port,
                username=username,
                password=password
            )

    def close(self):
        ...

    @WebhookAdapterInterface.batch
    @WebhookAdapterInterface.retry
    async def deliver_async(self, payload: Any):
        delivery_id = self.generate_delivery_id()
        key = self.model.stream_key
        match self.model.mode:
            case 'stream':
                await self.conn.xadd(key, {"id": delivery_id, "payload": json.dumps(payload)})
            case "list":
                await self.conn.lpush(key, json.dumps({"id": delivery_id, "payload": payload}))
            case 'pubsub':
                await self.conn.publish(key, json.dumps(payload))
        return 200, b"OK"

    @WebhookAdapterInterface.retry
    def deliver(self, payload: Any):
        delivery_id = self.generate_delivery_id()
        key = self.model.stream_key
        match self.model.mode:
            case 'stream':
                self.sync_conn.xadd(key, {"id": delivery_id, "payload": json.dumps(payload)})
            case 'list':
                self.sync_conn.lpush(key, json.dumps({"id": delivery_id, "payload": payload}))
            case 'pubsub':
                self.sync_conn.publish(key, json.dumps(payload))
        return 200, b"OK"