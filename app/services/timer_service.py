from app.definition._service import DEFAULT_BUILD_STATE, BaseService, Service
from app.interface.timers import SchedulerInterface
from app.services.config_service import ConfigService

@Service()
class TimerService(BaseService,SchedulerInterface):
    def __init__(self,configService:ConfigService):
        super().__init__()
        SchedulerInterface.__init__(self,)
        self.configService = configService

    def build(self,build_state=DEFAULT_BUILD_STATE):
        ...