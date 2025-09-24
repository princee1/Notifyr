
from typing import Union
from typing_extensions import Literal
from app.classes.profiles import ProfileDoesNotExistsError
from app.definition import _service
from app.interface.timers import SchedulerInterface
from app.services.aws_service import AmazonSESService
from app.services.config_service import ConfigService
from app.services.database_service import MongooseService, RedisService
from app.services.email.email_api_service import EmailAPIService
from app.services.email.mail_protocol_service import IMAPEmailMiniService, SMTPEmailMiniService
from app.services.logger_service import LoggerService
from app.services.profile_service import ProfileManagerService
from app.services.reactive_service import ReactiveService
from app.services.secret_service import HCVaultService
from app.utils.tools import Mock
from app.interface.email import EmailReadInterface, EmailSendInterface

available_state= HCVaultService._ping_available_state.copy()

class EmailService(_service.BaseMiniServiceManager):

    def verify_dependency(self):
        if self.profilesService.service_status not in available_state:
            raise _service.ServiceNotAvailableError

    async def async_verify_dependency(self):
        async with self.profilesService.statusLock.reader:
            if self.profilesService.service_status not in available_state:
                return False
            return True

    def __init__(self,profileService:ProfileManagerService):
        super().__init__()
        self.profilesService = profileService

@_service.Service
class EmailSenderService(EmailService):
    # BUG cant resolve an abstract class

    def __init__(self, configService: ConfigService,loggerService:LoggerService,redisService:RedisService,profileService:ProfileManagerService) -> None:
        super().__init__(profileService)
        self.configService = configService
        self.loggerService = loggerService
        self.redisService = redisService

    def select(self,profilesId:str)->EmailSendInterface:
       ...

    def build(self,build_state=_service.DEFAULT_BUILD_STATE):
        ...

@_service.Service
class EmailReaderService(EmailService):
    def __init__(self, configService: ConfigService,reactiveService:ReactiveService,loggerService:LoggerService,profilesService:ProfileManagerService) -> None:
        super().__init__(profilesService)
        self.configService = configService
        self.reactiveService = reactiveService
        self.loggerService = loggerService


    def build(self, build_state = _service.DEFAULT_BUILD_STATE):
        ...

    def start_jobs(self):
        for p in self.MiniServiceStore.values():
            p.schedule()

    def cancel_jobs(self):
        for p in self.MiniServiceStore.values():
            p.shutdown()