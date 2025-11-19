import asyncio
import json
import random
from typing import Any, Self
import uuid

from aiohttp_retry import Callable
from app.definition._error import BaseError
from app.errors.webhook_error import DeliveryError, NonRetryableError
from app.interface.timers import IntervalParams, SchedulerInterface
from app.models.webhook_model import BatchConfig, WebhookProfileModel
from aiorwlock import RWLock
from app.utils.helper import generateId

class WebhookAdapterInterface(SchedulerInterface):

    RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}

    @staticmethod
    def batch(func:Callable):
        
        async def w(self:Self,payload:Any,**kwargs):
            if self.is_batch_allowed:
                return await self.add(payload)
            return await self.deliver_async(payload,**kwargs)

        return w

    @staticmethod
    def retry(func:Callable):
        
        def s(self:Self,payload:Any,**kwargs):
            attempt = 0
            while attempt<=self.model.max_attempt:
                try:
                    code,_= func(self,payload,**kwargs)
                    if code in self.model._retry_statuses:
                        attempt+=1
                    return code,_
                except DeliveryError as e:
                    attempt+=1
                except NonRetryableError as e:
                    return None,None
            
        async def a(self:Self,payload,**kwargs):
            attempt = 0
            while attempt<=self.model.max_attempt:
                try:
                    code,_= await func(self,payload,**kwargs)
                    if code in self.model._retry_statuses:
                        attempt+=1
                    return code,_
                except DeliveryError as e:
                    attempt+=1
                except NonRetryableError as e:
                    return None,None

        return a if asyncio.iscoroutinefunction(func) else s

    def __init__(self):
        super().__init__(None)
        self.is_batch_allowed = self.model.batch_config!=None
        self.buffers: dict[str,dict] ={}
        self.batch_lock = RWLock()
        if self.is_batch_allowed:
            self.interval_schedule(IntervalParams(),self.flush)

    @property
    def model(self)->WebhookProfileModel:
        ...

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
    
    async def deliver_async(self,payload:Any|list[Any]):
        ...

    def deliver(self,payload:Any|list[Any]):
        ...
    
    async def add(self,payload: dict):
        if not self.is_batch_allowed:
            return 

        async with self.batch_lock.reader:
            _id = generateId(10,True)
            self.buffers[_id] = payload
            _len = len(self.buffers)

        if _len >= self.model.batch_config["max_batch"]:
            await self.flush()

    async def flush(self):
        if not self.is_batch_allowed:
            return 
        if not self.buffers:
            return
        async with self.batch_lock.writer:
            batch = self.buffers.copy()
            self.buffers.clear()
            batch = batch.values()
        if self.model.batch_config['mode'] == 'single':
            await self.deliver_async(batch)
        else:
            await self.deliver_async(batch)
        
    def close(self):
        ...

    async def start(self):
        ...