from prometheus_client import Counter, Gauge, Histogram
from app.definition._service import DEFAULT_BUILD_STATE, BaseService, Service
from app.errors.service_error import BuildWarningError
from app.interface.timers import SchedulerInterface
from app.services.config_service import ConfigService, ProcessWorkerService
from app.services.database_service import MongooseService, RedisService

@Service()
class TaskService(BaseService,SchedulerInterface):

    def __init__(self, configService: ConfigService,redisService:RedisService,mongooseService:MongooseService,processWorkerService:ProcessWorkerService):
        self.configService = configService
        self.redisService = redisService
        self.mongooseService = mongooseService
        self.processWorkerService = processWorkerService
        super().__init__()
        SchedulerInterface.__init__(self,None)

    def build(self,build_state=DEFAULT_BUILD_STATE):

        if build_state == DEFAULT_BUILD_STATE:
            try:
                self.connection_count = Gauge('http_connections','Active Connection Count')
                self.request_latency = Histogram("http_request_duration_seconds", "Request duration in seconds")
                self.connection_total = Counter('total_http_connections','Total Request Received')
                self.background_task_count = Gauge('background_task','Active Background Working Task')
            except:
                raise BuildWarningError        
            
    async def async_pingService(self,infinite_wait:bool,**kwargs):  # TODO
        ...
    
