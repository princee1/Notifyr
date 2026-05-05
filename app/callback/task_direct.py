from app.classes.scheduler import Scheduler
from app.container import Get
from app.services.worker.celery_service import CeleryService
from app.services.database.redis_service import RedisService
from app.services.cost_service import CostService
from app.services.agent.remote_agent_service import RemoteAgentService

async def Send_Ntfr_Task_Direct(scheduler:Scheduler):
    celeryService = Get(CeleryService)
    redisService = Get(RedisService)
    costService = Get(CostService)
    remoteAgentService = Get(RemoteAgentService)

    async with celeryService.statusLock.reader as l:
        ...
