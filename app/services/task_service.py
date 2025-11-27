import asyncio
from typing import Optional
from app.definition._service import DEFAULT_BUILD_STATE, BaseService, Service
from app.errors.service_error import NotBuildedError
from app.interface.timers import SchedulerInterface,RedisJobStore,MemoryJobStore,MongoDBJobStore,AsyncIOExecutor,ThreadPoolExecutor
from app.services.config_service import ConfigService, ProcessWorkerService
from app.services.database_service import MongooseService, RedisService
from app.services.secret_service import HCVaultService
from app.utils.constant import MongooseDBConstant, RedisConstant

# configuration
LEADER_LOCK_KEY = "apscheduler:leader_lock"
LEADER_LOCK_TTL = 10
LEADER_RENEW_INTERVAL = 3.0 
SCHEDULER_JOBSTORE_PREFIX = "apscheduler:"

@Service()
class TaskService(BaseService,SchedulerInterface):

    def __init__(self, configService: ConfigService,vaultService:HCVaultService,processWorkerService:ProcessWorkerService,redisService:RedisService,mongooseService:MongooseService):
        super().__init__()
        self.configService = configService
        self.processWorkerService = processWorkerService
        self.vaultService = vaultService
        self.redisService = redisService
        self.mongooseService = mongooseService
        
        self._leader = False
        self._leader_task: Optional[asyncio.Task] = None
        self._renew_task: Optional[asyncio.Task] = None
        self._stop = False

    def build(self, build_state = DEFAULT_BUILD_STATE):

        self.instance_id = f'{self.configService.INSTANCE_ID}'
        
        self.redis = self.redisService.db['celery']
        jobstores = {
            "redis": RedisJobStore(
                host=self.redis.connection_pool.connection_kwargs.get("host", "localhost"),
                port=self.redis.connection_pool.connection_kwargs.get("port", 6379),db=RedisConstant.CELERY_DB,
                # some Redis jobstores accept prefix arg; see your plugin's API
                jobs_key=f"{SCHEDULER_JOBSTORE_PREFIX}jobs",run_times_key=f"{SCHEDULER_JOBSTORE_PREFIX}run_times",),
            'memory':MemoryJobStore(),
            'mongo':MongoDBJobStore(MongooseDBConstant.DATABASE_NAME,collection=MongooseDBConstant.TASKS_COLLECTION,client=self.mongooseService.sync_client)
        }
        SchedulerInterface.__init__(self,None,jobstores,'redis',executor='asyncio-executor',replace_existing=True,coalesce=True,thread_pool_count=50)

    async def start(self):
        if not self._builded:
            raise NotBuildedError()
        
        self._stop = False
        self._leader_task = asyncio.create_task(self._leader_loop())

    async def stop(self):
        self._stop = True
        if self._leader_task:
            self._leader_task.cancel()
        if self._renew_task:
            self._renew_task.cancel()
        await self._stop_scheduler()
        await self.redis.close()

    async def _leader_loop(self):
        """
        Try to obtain the Redis lock. If we get it -> become leader and start scheduler.
        Keep renewing lock periodically. If we lose the lock -> stop scheduler and try again.
        """
        try:
            while not self._stop:
                got = await self._try_acquire_lock()
                if got and not self._leader:
                    # became leader
                    self._leader = True
                    await self._start_scheduler()
                    # start renewal task
                    self._renew_task = asyncio.create_task(self._renew_lock_loop())
                elif not got and self._leader:
                    # lost leadership
                    self._leader = False
                    if self._renew_task:
                        self._renew_task.cancel()
                    await self._stop_scheduler()
                # if not leader, keep retrying every couple seconds
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            return

    async def _try_acquire_lock(self) -> bool:
        # SET key value NX EX ttl
        # store instance_id as value so only renewer can extend
        res = await self.redis.set(
            LEADER_LOCK_KEY, self.instance_id, nx=True, ex=LEADER_LOCK_TTL
        )
        return bool(res)

    async def _renew_lock_loop(self):
        try:
            while not self._stop and self._leader:
                # renew by checking value then extending (simple pattern)
                val = await self.redis.get(LEADER_LOCK_KEY)
                if val is None or val.decode() != self.instance_id:
                    # someone else took lock
                    self._leader = False
                    await self._stop_scheduler()
                    return
                # extend TTL using expire (or a Lua script for atomic check+expire)
                await self.redis.expire(LEADER_LOCK_KEY, LEADER_LOCK_TTL)
                await asyncio.sleep(LEADER_RENEW_INTERVAL)
        except asyncio.CancelledError:
            return

    async def _start_scheduler(self):
        SchedulerInterface.start(self)
        print(f"[{self.instance_id}] Became leader and started scheduler.")

    async def _stop_scheduler(self):
        self.shutdown(wait=False)
        print(f"[{self.instance_id}] Stopped scheduler (lost leadership).")