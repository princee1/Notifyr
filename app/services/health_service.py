from app.definition._service import InjectWithCondition, Service,BaseService
from app.definition._service import Service
from app.services.config_service import ConfigService
from app.services.notification_service import DiscordService, NotificationService,SystemNotificationService
import psutil

from app.services.rate_limiter_service import RateLimiterService
from app.utils.constant import ConfigAppConstant

def resolve_notification_service(configService:ConfigService):
    return DiscordService if True else SystemNotificationService

@Service
class HealthService(BaseService):
    
    def __init__(self,configService:ConfigService,discordService:DiscordService,rateLimiterService:RateLimiterService):
        super().__init__()
        self.configService = configService
        self.notificationService = discordService
        self.rateLimiterService = rateLimiterService

    def build(self):
        self.process = psutil.Process()
           
    @property
    def cpu_count(self):
        return psutil.cpu_count(logical=True)

    @property
    def ram_size_gb(self):
        return round(psutil.virtual_memory().total / (1024 ** 3), 2)  # Convert bytes to GB

    @property
    def process_cpu_metrics(self):
        return self.process.cpu_percent(interval=1.0)
    
    @property
    def process_cpu_times(self):
        return self.process.cpu_times()._asdict()
    
    @property
    def workers_count(self):
        return 1

    @property
    def weight(self):
        return 1

    @property
    def notifyr_app_info(self)->dict:
        return {
            'InstanceId':self.configService.INSTANCE_ID,
            'ParentPid':self.configService.PARENT_PID,
            'Spec':{
                'CpuCount':self.cpu_count,
                'Ram':self.ram_size_gb,
                'Weight':self.weight,
                'Workers':self.workers_count
            }

        }
