
from typing import Union
from typing_extensions import Literal
from app.classes.profiles import ProfileDoesNotExistsError
from app.definition import _service
from app.interface.profile import ProfileInterface
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

@_service.Service
class EmailSenderService(_service.BaseService,ProfileInterface):
    # BUG cant resolve an abstract class
    def __init__(self, configService: ConfigService,loggerService:LoggerService,redisService:RedisService,profileService:ProfileManagerService) -> None:
        super().__init__()
        self.configService = configService
        self.loggerService = loggerService
        self.redisService = redisService
        self.profilesService = profileService
       
        self.profiles:dict[str,Union[EmailSendInterface,_service.BaseService]] = {
        }

    def verify_dependency(self):
        ...

    def select(self,profilesId)->EmailSendInterface:
        p = self.profiles.get(profilesId,None)
        if p == None:
            raise ProfileDoesNotExistsError
        if p.service_status != _service.ServiceStatus.AVAILABLE:
            raise # TODO


    def build(self,build_state=_service.DEFAULT_BUILD_STATE):
        ...

@_service.Service
class EmailReaderService(_service.BaseService,ProfileInterface):
    def __init__(self, configService: ConfigService,reactiveService:ReactiveService,loggerService:LoggerService,profilesService:ProfileManagerService) -> None:
        super().__init__()
        self.configService = configService
        self.reactiveService = reactiveService
        self.loggerService = loggerService
        self.profilesService = profilesService

        self.profiles:dict[str,EmailReadInterface | _service.BaseService] = {}


    def verify_dependency(self):
        return super().verify_dependency()

    def build(self, build_state = _service.DEFAULT_BUILD_STATE):
        ...

    def start_jobs(self):
        for p in self.profiles.values():
            p.start_jobs()

    
    def cancel_jobs(self):
        for p in self.profiles.values():
            p.cancel_jobs()