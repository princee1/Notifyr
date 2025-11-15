import json
import random
from typing import Any, Generic, TypeVar
import uuid
from app.definition._interface import Interface
from app.models.webhook_model import WebhookProfileModel


class WebhookAdapterInterface(Interface):

    RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}

    def next_backoff(attempt: int, base: float = 1.0, max_backoff: float = 60.0):
        raw = base * (2 ** (attempt - 1))
        raw = min(raw, max_backoff)
        jitter = random.uniform(0, raw * 0.2)
        return raw + jitter

    @staticmethod
    def json_bytes(payload:Any)->bytes:
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    @staticmethod
    def generate_delivery_id()->str:
        return str(uuid.uuid4())
    
    async def async_deliver(self,payload:Any):
        ...

    async def sync_deliver(self,payload:Any):
        ...

    async def batch(self):
        ...
    
    async def flush(self):
        ...
    
    def ping(self,):
        ...

    async def close(self):
        ...

    async def start(self):
        ...