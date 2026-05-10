from app.classes.scheduler import Scheduler
from app.container import Get
from app.services.worker.celery_service import CeleryService
from app.services import RedisService
from app.services import CostService
from app.services import ChatService

async def Send_Ntfr_Task_Direct(scheduler:Scheduler,*args,**kwargs):
    celeryService = Get(CeleryService)
    redisService = Get(RedisService)
    costService = Get(CostService)
    chatService = Get(ChatService)

    async with celeryService.statusLock.reader as l:
        ...
