import asyncio
from random import randint, random
from typing import Optional
from app.classes.celery import SchedulerModel, TaskType
from app.definition._service import DEFAULT_BUILD_STATE, BaseService, Service, ServiceStatus
from app.errors.aps_error import APSJobDoesNotExists
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.jobstores.mongodb import MongoDBJobStore
from app.errors.service_error import BuildOkError, NotBuildedError, ServiceNotAvailableError
from app.interface.timers import SchedulerInterface,MemoryJobStore
from app.services.config_service import ConfigService, UvicornWorkerService
from app.services.cost_service import CostService
from app.services.database.mongoose_service import MongooseService
from app.services.database.redis_service import RedisService
from app.services.logger_service import LoggerService
from app.services.secret_service import HCVaultService
from app.utils.constant import MongooseDBConstant, RedisConstant, CeleryConstant
from app.utils.tools import RunInThreadPool
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers import (
    SchedulerAlreadyRunningError,
    SchedulerNotRunningError,
)

CeleryConstant.BACKEND_KEY_PREFIX


# configuration
LEADER_LOCK_KEY = f"apscheduler@leader_lock"
LEADER_LOCK_TTL = 600
LEADER_LOCK_TTL_LOWER_BOUND = int(LEADER_LOCK_TTL * 0.50)
LEADER_LOCK_TTL_UPPER_BOUND = int(LEADER_LOCK_TTL * 5.50)

LEADER_RENEW_INTERVAL = 3.0 
SCHEDULER_JOBSTORE_PREFIX = f"{CeleryConstant.BACKEND_KEY_PREFIX}apscheduler"

@Service()
class TaskService(BaseService,SchedulerInterface):
    _schedule_type_supported = {TaskType.DATETIME,TaskType.INTERVAL,TaskType.TIMEDELTA,TaskType.CRONTAB}


    def __init__(self, configService: ConfigService,vaultService:HCVaultService,processWorkerService:UvicornWorkerService,redisService:RedisService,mongooseService:MongooseService,loggerService:LoggerService,costService:CostService):
        super().__init__()
        self.configService = configService
        self.uvicornWorkerService = processWorkerService
        self.vaultService = vaultService
        self.redisService = redisService
        self.mongooseService = mongooseService
        self.loggerService = loggerService
        self.costService = costService
        
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
        
        redis_client = self.redisService.db['celery']
        self.redis_client = self.redisService.db['events']
        self.mongo_client = self.mongooseService.sync_client
        jobstores = {
            "redis": RedisJobStore(
                host=redis_client.connection_pool.connection_kwargs.get("host", "localhost"),
                port=redis_client.connection_pool.connection_kwargs.get("port", 6379),
                db=RedisConstant.CELERY_DB,
                jobs_key=f"{SCHEDULER_JOBSTORE_PREFIX}/jobs@",
                run_times_key=f"{SCHEDULER_JOBSTORE_PREFIX}:run_times",
                username=redis_client.connection_pool.connection_kwargs.get('username'),
                password=redis_client.connection_pool.connection_kwargs.get('password')
                ),
            'memory':MemoryJobStore(),
            'mongodb':MongoDBJobStore(
                MongooseDBConstant.DATABASE_NAME,
                collection=MongooseDBConstant.TASKS_COLLECTION,
                client=self.mongo_client
                )
        }
        jobstore = self.configService.APS_JOBSTORE if not self.fallback_to_memory else 'memory'
        SchedulerInterface.__init__(self,None,jobstores,jobstore,executor='asyncio-executor',replace_existing=True,coalesce=True,thread_pool_count=50)

    def start(self):
        if self.configService.APS_JOBSTORE == 'memory' or self.fallback_to_memory:
            return 
        if not self._builded:
            raise NotBuildedError()
        self._stop = False
        SchedulerInterface.start(self)
        self.pause()
        self._leader_task = asyncio.create_task(self._leader_loop())

    def shutdown(self):
        if self.configService.APS_JOBSTORE == 'memory' or self.fallback_to_memory:
            return 
        self._stop = True
        if self._leader_task:
            self._leader_task.cancel()
        SchedulerInterface.shutdown(self)
    
    async def resume(self):
        if self.configService.APS_JOBSTORE != 'mongodb':
            SchedulerInterface.resume(self)
            return
        async with self.mongooseService.statusLock.reader:
            SchedulerInterface.resume(self)
    
    async def _leader_loop(self):
        """
        Try to obtain the Redis lock. If we get it -> become leader and start scheduler.
        Keep renewing lock periodically. If we lose the lock -> stop scheduler and try again.
        """
        await asyncio.sleep(random()*3)
        try:
            while not self._stop:
                got = await self._try_acquire_lock()
                if got:
                    if not self._leader:
                        # became leader
                        await self.resume()
                        print(f"[{self.uvicornWorkerService.INSTANCE_ID}] Became leader and started scheduler.")
                        self._leader = True
                    else:
                        print(f"[{self.uvicornWorkerService.INSTANCE_ID}] Renew the leadership lock")
                        await self.redis_client.expire(LEADER_LOCK_KEY, LEADER_LOCK_TTL)
                else:
                    val = await self.redis_client.get(LEADER_LOCK_KEY)
                    if val is None:
                        print(f"[{self.uvicornWorkerService.INSTANCE_ID}] Somehow the no one has the lock... Attempting right away")
                        continue
                    val = val.decode()
                    if val != self.uvicornWorkerService.INSTANCE_ID:
                        # someone else took lock
                        if self._leader:
                            self.pause()
                            print(f"[{self.uvicornWorkerService.INSTANCE_ID}] Stopped scheduler (lost leadership). Holder: {val}")
                            self._leader = False
                        else:
                            ...
                            #print(f"[{self.uvicornWorkerService.INSTANCE_ID}] Could not get the leadership, Hold by {val}")
                    else:
                        #print(f"[{self.uvicornWorkerService.INSTANCE_ID}] Extend the leadership lock")
                        await self.redis_client.expire(LEADER_LOCK_KEY, LEADER_LOCK_TTL)

                await asyncio.sleep(LEADER_LOCK_TTL + (randint(LEADER_LOCK_TTL_LOWER_BOUND,LEADER_LOCK_TTL_UPPER_BOUND)))
        except asyncio.CancelledError as e:
            ...
        except SchedulerNotRunningError as e:
            print(f"[{self.uvicornWorkerService.INSTANCE_ID}] Schdeuler Not running Error {e.args}")
            return
        except Exception as e:
            print(f"[{self.uvicornWorkerService.INSTANCE_ID}] Error: Class {e.__class__}, {e} {e.args}")
            return

    async def _try_acquire_lock(self) -> bool:
        # SET key value NX EX ttl
        # store instance_id as value so only renewer can extend
        res = await self.redis_client.set(
            LEADER_LOCK_KEY, self.uvicornWorkerService.INSTANCE_ID, nx=True, ex=LEADER_LOCK_TTL
        )
        
        return bool(res)

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
            return self._scheduler.remove_all_jobs(self.jobstore)
        else:
            try:
                return self._scheduler.remove_job(job_id,self.jobstore)
            except JobLookupError as e:
                raise APSJobDoesNotExists(job_id,*e.args)
            
    @RunInThreadPool
    def pause_job(self, job_id):
        return SchedulerInterface.pause_job(self,job_id,self.jobstore)

    @RunInThreadPool
    def resume_job(self,job_id):
        return SchedulerInterface.resume_job(self,job_id,self.jobstore)
