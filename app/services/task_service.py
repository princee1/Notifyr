import asyncio
from random import randint
from typing import Optional
from app.classes.celery import SchedulerModel, TaskType
from app.definition._service import DEFAULT_BUILD_STATE, BaseService, Service, ServiceStatus
from app.errors.aps_error import APSJobDoesNotExists
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.jobstores.mongodb import MongoDBJobStore
from app.errors.service_error import BuildOkError, NotBuildedError, ServiceNotAvailableError
from app.interface.timers import SchedulerInterface,MemoryJobStore
from app.services.config_service import ConfigService, UvicornWorkerService
from app.services.database.mongoose_service import MongooseService
from app.services.database.redis_service import RedisService
from app.services.logger_service import LoggerService
from app.services.secret_service import HCVaultService
from app.utils.constant import MongooseDBConstant, RedisConstant
from app.utils.tools import RunInThreadPool
from apscheduler.jobstores.base import JobLookupError


# configuration
LEADER_LOCK_KEY = "apscheduler:leader_lock"
LEADER_LOCK_TTL = 300
LEADER_RENEW_INTERVAL = 3.0 
SCHEDULER_JOBSTORE_PREFIX = "apscheduler:"

@Service()
class TaskService(BaseService,SchedulerInterface):
    _schedule_type_supported = {TaskType.DATETIME,TaskType.INTERVAL,TaskType.TIMEDELTA,TaskType.CRONTAB}


    def __init__(self, configService: ConfigService,vaultService:HCVaultService,processWorkerService:UvicornWorkerService,redisService:RedisService,mongooseService:MongooseService,loggerService:LoggerService):
        super().__init__()
        self.configService = configService
        self.uvicornWorkerService = processWorkerService
        self.vaultService = vaultService
        self.redisService = redisService
        self.mongooseService = mongooseService
        self.loggerService = loggerService
        
        self._leader = False
        self._leader_task: Optional[asyncio.Task] = None
        self._stop = False
        self.fallback_to_memory = False

    async def pingService(self, infinite_wait, data, profile = None, as_manager = False, **kwargs):
        if kwargs.get('__task_aps_availability__',False) and self.service_status != ServiceStatus.AVAILABLE:
            raise ServiceNotAvailableError()   

        scheduler:SchedulerModel = kwargs.get('scheduler',None)
        if scheduler:
            if  self.configService.CELERY_WORKERS_EXPECTED < 1 and self.service_status != ServiceStatus.AVAILABLE and scheduler.task_type in self._schedule_type_supported:
                raise ServiceNotAvailableError()   

    def verify_dependency(self):
        #self._builded = True
        if not self.configService.APS_ACTIVATED:
            raise BuildOkError

        if self.configService.APS_JOBSTORE == 'mongodb' and  self.mongooseService.service_status != ServiceStatus.AVAILABLE:
            self.fallback_to_memory = True
        
        if  self.configService.APS_JOBSTORE == 'redis' and self.redisService.service_status != ServiceStatus.AVAILABLE:
            self.fallback_to_memory = True

    def build(self, build_state = DEFAULT_BUILD_STATE):
        if self._builded:
            self.shutdown(False)
        
        self.redis = self.redisService.db['celery']
        jobstores = {
            "redis": RedisJobStore(
                host=self.redis.connection_pool.connection_kwargs.get("host", "localhost"),
                port=self.redis.connection_pool.connection_kwargs.get("port", 6379),db=RedisConstant.CELERY_DB,
                # some Redis jobstores accept prefix arg; see your plugin's API
                jobs_key=f"{SCHEDULER_JOBSTORE_PREFIX}jobs",run_times_key=f"{SCHEDULER_JOBSTORE_PREFIX}run_times",),
            'memory':MemoryJobStore(),
            'mongodb':MongoDBJobStore(MongooseDBConstant.DATABASE_NAME,collection=MongooseDBConstant.TASKS_COLLECTION,client=self.mongooseService.sync_client)
        }
        jobstore = self.configService.APS_JOBSTORE if not self.fallback_to_memory else 'memory'
        SchedulerInterface.__init__(self,None,jobstores,jobstore,executor='asyncio-executor',replace_existing=True,coalesce=True,thread_pool_count=50)

    async def start(self):
        if self.configService.APS_JOBSTORE == 'memory' or self.fallback_to_memory:
            return 
        if not self._builded:
            raise NotBuildedError()
        self._stop = False
        self._leader_task = asyncio.create_task(self._leader_loop())

    async def stop(self):
        if self.configService.APS_JOBSTORE == 'memory' or self.fallback_to_memory:
            return 
        self._stop = True
        if self._leader_task:
            self._leader_task.cancel()
        await self._stop_scheduler()

    async def _leader_loop(self):
        """
        Try to obtain the Redis lock. If we get it -> become leader and start scheduler.
        Keep renewing lock periodically. If we lose the lock -> stop scheduler and try again.
        """
        try:
            while not self._stop:
                got = await self._try_acquire_lock()
                if got:
                    if not self._leader:
                        # became leader
                        self._leader = True
                        await self._start_scheduler()
                    else:
                        await self.redis.expire(LEADER_LOCK_KEY, LEADER_LOCK_TTL)
                        
                else:
                    val = await self.redis.get(LEADER_LOCK_KEY)
                    if val is None:
                        print(f"[{self.uvicornWorkerService.INSTANCE_ID}] Somehow the no one has the lock... Attempting right away")
                        continue
                    if val.decode() != self.uvicornWorkerService.INSTANCE_ID:
                        # someone else took lock
                        await self._stop_scheduler()
                        self._leader = False
                    else:
                        await self.redis.expire(LEADER_LOCK_KEY, LEADER_LOCK_TTL)

                # if not leader, keep retrying every couple seconds
                await asyncio.sleep(LEADER_LOCK_TTL * 1.20 + (randint(5,15)))
        except asyncio.CancelledError:
            return

    async def _try_acquire_lock(self) -> bool:
        # SET key value NX EX ttl
        # store instance_id as value so only renewer can extend
        res = await self.redis.set(
            LEADER_LOCK_KEY, self.uvicornWorkerService.INSTANCE_ID, nx=True, ex=LEADER_LOCK_TTL
        )
        
        return bool(res)

    async def _start_scheduler(self):
        SchedulerInterface.start(self)
        print(f"[{self.uvicornWorkerService.INSTANCE_ID}] Became leader and started scheduler.")

    async def _stop_scheduler(self):
        self.shutdown(wait=False)
        print(f"[{self.uvicornWorkerService.INSTANCE_ID}] Stopped scheduler (lost leadership).")

    @RunInThreadPool
    def get_jobs(self,job_id:str= None):
        if job_id != None:
            job = self._scheduler.get_job(job_id,self.jobstore)
            if job == None:
                raise APSJobDoesNotExists(job_id)
            return [job]
        else:
            return self._scheduler.get_jobs(self.jobstore)

    @RunInThreadPool
    def cancel_job(self,job_id:str=None):
        if job_id == None:
            self._scheduler.remove_all_jobs(self.jobstore)
        else:
            try:
                self._scheduler.remove_job(job_id,self.jobstore)
            except JobLookupError as e:
                raise APSJobDoesNotExists(job_id,*e.args)