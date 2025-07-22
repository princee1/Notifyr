from app.definition._service import InjectWithCondition, Service,BaseService
#from app.services.celery_service import CeleryService, TaskService
from app.services.config_service import ConfigService
from app.services.notification_service import DiscordService, NotificationService,SystemNotificationService
import psutil

from app.utils.constant import ConfigAppConstant

def resolve_notification_service(configService:ConfigService):
    return DiscordService if True else SystemNotificationService

@Service
class HealthService(BaseService):
    
    def __init__(self,configService:ConfigService,discordService:DiscordService):
        super().__init__()
        self.configService = configService
        self.notificationService = discordService
        self._capabilities = []

    def build(self):
        self.process = psutil.Process()
    
    def init_capabilities(self,ressources):
        for r in ressources:
            meta = getattr(r,'meta',None)
            if meta == None:
                continue
            path:str = meta['prefix']
            self._capabilities.append(path)
               
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
    def raw_capabilities(self):
        return self.configService.config_json_app.data[ConfigAppConstant.APPS_KEY][self.configService.app_name][ConfigAppConstant.RESSOURCE_KEY]

    @property
    def capabilities(self):
        return self._capabilities