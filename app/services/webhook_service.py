import asyncio
import random
from app.definition._service import BaseMiniServiceManager, BaseService, LinkDep, Service, ServiceStatus
from app.services.profile_service import ProfileService
from app.services.reactive_service import ReactiveService
from .config_service import ConfigService


# core/batching.py
import asyncio
from collections import defaultdict
from typing import Dict, List, Callable

class BatchManager:
    def __init__(self, flush_interval=2.0):
        self.flush_interval = flush_interval
        self.buffers: Dict[str, List[dict]] = defaultdict(list)
        self.callbacks: Dict[str, Callable] = {}
        self.running = False

    def register(self, endpoint_id: str, callback):
        """callback(endpoint, batch_payloads) will be called on flush."""
        self.callbacks[endpoint_id] = callback

    async def add(self, endpoint_id: str, payload: dict, max_batch: int = 50):
        self.buffers[endpoint_id].append(payload)
        if len(self.buffers[endpoint_id]) >= max_batch:
            await self.flush(endpoint_id)

    async def flush(self, endpoint_id: str):
        if not self.buffers[endpoint_id]:
            return
        batch = self.buffers[endpoint_id]
        self.buffers[endpoint_id] = []
        await self.callbacks[endpoint_id](batch)

    async def loop(self):
        self.running = True
        while self.running:
            await asyncio.sleep(self.flush_interval)
            for endpoint_id in list(self.buffers.keys()):
                await self.flush(endpoint_id)


@Service(
    links=[LinkDep(ProfileService,to_build=True,to_destroy=True)]
)
class WebhookService(BaseMiniServiceManager):
    
    def __init__(self,configService:ConfigService,profileService:ProfileService,reactiveService:ReactiveService):
        super().__init__()
        self.configService = configService
        self.profileService = profileService
        self.reactiveService = reactiveService

    
    def build(self):
        ...


    