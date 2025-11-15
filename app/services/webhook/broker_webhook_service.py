import json
from typing import Any
from aiokafka import AIOKafkaProducer
import aiobotocore3 as aiobotocore_session
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService
from app.interface.webhook_adapter import WebhookAdapterInterface
from app.models.webhook_model import KafkaWebhookModel, RedisWebhookModel, SQSWebhookModel
from app.services.config_service import ConfigService
from app.services.profile_service import ProfileMiniService
from redis.asyncio import Redis,from_url as async_from_url
from redis import Redis as SyncRedis,from_url

# ---------- KafkaAdapter (aiokafka) ----------
class KafkaWebhookMiniService(BaseMiniService,WebhookAdapterInterface):

    def __init__(self,profileMiniService:ProfileMiniService[KafkaWebhookModel]):
        self.depService = profileMiniService
        super().__init__(profileMiniService,None)

    @property
    def model(self):
        return self.depService.model

    def build(self,build_state=DEFAULT_BUILD_STATE):

        bootstrap_servers  =self.model.bootstrap_servers
        client_id = self.model.client_id
        self.producer = AIOKafkaProducer(
            bootstrap_servers,
            client_id=client_id,
            acks=self.model.acks,
            compression_type=self.model.compression,
            enable_idempotence=self.model.enable_idempotence
            )
        self._started = False


    async def start(self):
        if not self._started:
            await self.producer.start()
            self._started = True

    async def stop(self):
        if self._started:
            await self.producer.stop()
            self._started = False

    async def deliver(self,payload: Any):
        await self.start()
        topic = self.model.topic
        key = self.model.key or self.generate_delivery_id()
        payload = self.json_bytes(payload)
        key=str(key).encode("utf-8")
        if self.model.send_and_wait:
            result = await self.producer.send_and_wait(topic, self.json_bytes(payload), key=str(key).encode("utf-8"))
        else:
            await self.producer.send(topic,)

        return 200, b"OK"


# ---------- SQSAdapter (aiobotocore) ----------
class SQSWebhookMiniService(BaseMiniService,WebhookAdapterInterface):

        def __init__(self,profileMiniService:ProfileMiniService[SQSWebhookModel]):
            self.depService = profileMiniService
            super().__init__(profileMiniService, None)

        @property
        def model(self):
            return self.depService.model

        def build(self,build_state=DEFAULT_BUILD_STATE):
            self._session = aiobotocore_session.get_session()

        async def deliver(self, payload: Any):
            
            delivery_id = self.default_gen_id()

            async with self._session.create_client("sqs", region_name=self.model.region,
                                                aws_secret_access_key=self.model.aws_access_key_id,
                                                aws_access_key_id=self.depService.credentials['aws_secret_access_key']) as client:
                body = json.dumps(payload)
                kwargs = {"QueueUrl": self.model.queue_url, "MessageBody": body}
                # support FIFO features if present in config
                if self.model.message_group_id_template:
                    kwargs["MessageGroupId"] = self.model.message_group_id_template
                    kwargs["MessageDeduplicationId"] = self.model.message_group_id_template or delivery_id
                resp = await client.send_message(**kwargs)
                # return 200 + stringified response for logging
                return 200, json.dumps(resp).encode("utf-8")


# ---------- RedisAdapter (streams, lists, pubsub) ----------
class RedisWebhookMiniService(BaseMiniService,WebhookAdapterInterface):

    def __init__(self,profileMiniService:ProfileMiniService[RedisWebhookModel],configService:ConfigService):
        self.configService = configService
        self.depService = profileMiniService
        super().__init__(profileMiniService, id)

    @property
    def model(self):
        return self.depService.model

    def build(self,build_state= DEFAULT_BUILD_STATE):
        if self.model.from_url:
            self.sync_conn = from_url(self.model.url)
            self.conn = async_from_url(self.model.url)
        else:
            self.sync_conn = SyncRedis(
                host=self.model.url,
                port=self.model.port,
                username=self.model.username,
                password=self.model.password
            )
            self.conn= Redis(
                host=self.model.url,
                port=self.model.port,
                username=self.model.username,
                password=self.model.password
            )

    def close(self):
        ...

    async def deliver(self, payload: Any):
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