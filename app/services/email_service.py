
from typing import Type
from app.definition import _service
from app.models.profile_model import IMAPProfileModel, ProfilModelValues, ProfileModel, SMTPProfileModel
from app.services.config_service import ConfigService
from app.services.database_service import MongooseService, RedisService
from app.services.email.email_api_service import EmailAPIService
from app.services.email.mail_protocol_service import IMAPEmailMiniService, SMTPEmailMiniService
from app.services.logger_service import LoggerService
from app.services.profile_service import ProfileMiniService, ProfileService
from app.services.reactive_service import ReactiveService
from app.utils.tools import Mock
from app.interface.email import EmailReadInterface, EmailSendInterface


class EmailService(_service.BaseMiniServiceManager):

    def verify_dependency(self):
        if self.profilesService.service_status not in _service.ACCEPTABLE_STATES:
            raise _service.BuildFailureError

    async def async_verify_dependency(self):
        async with self.profilesService.statusLock.reader:
            if self.profilesService.service_status not in _service.ACCEPTABLE_STATES:
                return False
            return True

    def __init__(self,profileService:ProfileService):
        super().__init__()
        self.profilesService = profileService
    
    def _create_mini_service(self,model,p)->ProfileMiniService | None:
        return 
    
    def build(self,build_state=_service.DEFAULT_BUILD_STATE):
        for i,p in self.profilesService.MiniServiceStore:
            model = type(p.model)
            miniService = self._create_mini_service(model,p)
            if miniService == None:
                continue
            miniService._builder(_service.BaseMiniService.QUIET_MINI_SERVICE,build_state,self.CONTAINER_LIFECYCLE_SCOPE)
            self.MiniServiceStore.add(miniService)

@_service.Service(
    links=[_service.LinkDep(ProfileService,to_build=True,to_destroy=True,)]
)
class EmailSenderService(EmailService):

    # BUG cant resolve an abstract class

    def __init__(self, configService: ConfigService,loggerService:LoggerService,redisService:RedisService,profileService:ProfileService) -> None:
        super().__init__(profileService)
        self.configService = configService
        self.loggerService = loggerService
        self.redisService = redisService

        self.MiniServiceStore = _service.MiniServiceStore[EmailSendInterface | _service.BaseMiniService]()

    def _create_mini_service(self, model, p):
        if model == SMTPProfileModel:
            return SMTPEmailMiniService(p,self.configService,self.loggerService,self.redisService)
        else:
            return None

    def select(self,profilesId:str)->EmailSendInterface:
       ...


@_service.Service(
    links=[_service.LinkDep(ProfileService,to_build=True,to_destroy=True,)]
)
class EmailReaderService(EmailService):

    def __init__(self, configService: ConfigService,reactiveService:ReactiveService,loggerService:LoggerService,profilesService:ProfileService,redisService:RedisService) -> None:
        super().__init__(profilesService)
        self.configService = configService
        self.reactiveService = reactiveService
        self.loggerService = loggerService
        self.redisService =redisService

        self.MiniServiceStore = _service.MiniServiceStore[EmailReadInterface|_service.BaseMiniService]()

    def _create_mini_service(self, model, p):
        if model == IMAPEmailMiniService:
            return IMAPEmailMiniService(p,self.configService,self.loggerService,self.reactiveService,self.redisService)
        else:
            return None

    def start_jobs(self):
        for id,p in self.MiniServiceStore:
            p.start()

    def cancel_jobs(self):
        for id,p in self.MiniServiceStore:
            p.shutdown()