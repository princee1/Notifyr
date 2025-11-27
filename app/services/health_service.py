from app.definition._service import Service,BaseService
from app.definition._service import Service
from app.services.config_service import ConfigService, UvicornWorkerService
import psutil
from app.services.cost_service import CostService
from app.utils.globals import PARENT_PID, PROCESS_PID


@Service()
class HealthService(BaseService):
    
    def __init__(self,configService:ConfigService,rateLimiterService:CostService,uvicornWorkerService:UvicornWorkerService):
        super().__init__()
        self.configService = configService
        self.rateLimiterService = rateLimiterService
        self.uvicornWorkerService = uvicornWorkerService

    def build(self,build_state=-1):
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
        return self.configService.server_config['workers']

    @property
    def weight(self):
        return 1

    @property
    def notifyr_app_info(self)->dict:
        return {
            'InstanceId':self.uvicornWorkerService.INSTANCE_ID,
            'ParentPid':PARENT_PID,
            'Pid':PROCESS_PID,
            'Spec':{
                'CpuCount':self.cpu_count,
                'Ram':self.ram_size_gb,
                'Weight':self.weight,
                'Workers':self.workers_count
            }

        }
