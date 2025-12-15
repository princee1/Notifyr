
from typing import Type
from app.definition import _service
from app.models.communication_model import IMAPProfileModel, SMTPProfileModel
from app.services.config_service import ConfigService
from app.services.database_service import MongooseService, RedisService
#efrom app.services.email.api_email_service import EmailAPIService
from app.services.email.protocol_email_service import IMAPEmailMiniService, SMTPEmailMiniService
from app.services.logger_service import LoggerService
from app.services.profile_service import ProfileMiniService, ProfileService
from app.services.reactive_service import ReactiveService
from app.utils.tools import Mock
from app.interface.email import EmailReadInterface, EmailSendInterface


class EmailService(_service.BaseMiniServiceManager):

    ACCEPTABLE_MODEL:set = ...

    def __init_subclass__(cls):
        setattr(cls,'ACCEPTABLE_MODEL',cls.ACCEPTABLE_MODEL.copy())
        return super().__init_subclass__()

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
    
    def _create_mini_service(self,model,profile)->ProfileMiniService | None:
        return 
    
    def build(self,build_state=_service.DEFAULT_BUILD_STATE):
        
        count = self.profilesService.MiniServiceStore.filter_count(lambda p: p.model.__class__ in self.ACCEPTABLE_MODEL )
        state_counter = self.StatusCounter(count)

        self.MiniServiceStore.clear()

        for i,p in self.profilesService.MiniServiceStore:
            model = p.model.__class__
            miniService = self._create_mini_service(model,p)
            if miniService == None:
                continue
            miniService._builder(_service.BaseMiniService.QUIET_MINI_SERVICE,build_state,self.CONTAINER_LIFECYCLE_SCOPE)
            state_counter.count(miniService)
            self.MiniServiceStore.add(miniService)

        super().build(state_counter)


@_service.Service(
    links=[_service.LinkDep(ProfileService,to_build=True,to_destroy=True,)]
)
class EmailSenderService(EmailService):

    # BUG cant resolve an abstract class

    ACCEPTABLE_MODEL = {SMTPProfileModel}

    def __init__(self, configService: ConfigService,loggerService:LoggerService,redisService:RedisService,profileService:ProfileService) -> None:
        super().__init__(profileService)
        self.configService = configService
        self.loggerService = loggerService
        self.redisService = redisService

        self.MiniServiceStore = _service.MiniServiceStore[EmailSendInterface | _service.BaseMiniService](self.__class__.__name__)

    def _create_mini_service(self, model, profile):
        if model == SMTPProfileModel:
            return SMTPEmailMiniService(profile,self.configService,self.loggerService,self.redisService)
        else:
            return None



@_service.Service(
    links=[_service.LinkDep(ProfileService,to_build=True,to_destroy=True,)]
)
class EmailReaderService(EmailService):

    ACCEPTABLE_MODEL = {IMAPProfileModel}

    def __init__(self, configService: ConfigService,reactiveService:ReactiveService,loggerService:LoggerService,profilesService:ProfileService,redisService:RedisService) -> None:
        super().__init__(profilesService)
        self.configService = configService
        self.reactiveService = reactiveService
        self.loggerService = loggerService
        self.redisService =redisService

        self.MiniServiceStore = _service.MiniServiceStore[EmailReadInterface|_service.BaseMiniService](self.__class__.__name__)

    def _create_mini_service(self, model, profile):
        if model == IMAPProfileModel:
            return IMAPEmailMiniService(profile,self.configService,self.loggerService,self.reactiveService,self.redisService)
        else:
            return None

    def start_jobs(self):
        return 
        for id,p in self.MiniServiceStore:
            p.start()

    def cancel_jobs(self):
        return
        for id,p in self.MiniServiceStore:
            p.shutdown()