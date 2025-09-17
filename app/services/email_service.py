
from typing import Union
from typing_extensions import Literal
from app.definition import _service
from app.services.aws_service import AmazonSESService
from app.services.config_service import ConfigService
from app.services.database_service import MongooseService, RedisService
from app.services.email.email_api_service import EmailAPIService
from app.services.email.mail_protocol_service import IMAPEmailService, SMTPEmailService
from app.services.logger_service import LoggerService
from app.services.secret_service import HCVaultService
from app.utils.tools import Mock
from app.interface.email import EmailReadInterface, EmailSendInterface

@_service.Service
class EmailSenderService(_service.BaseService):
    # BUG cant resolve an abstract class
    def __init__(self, configService: ConfigService,loggerService:LoggerService,vaultService:HCVaultService,redisService:RedisService,mongooseService:MongooseService) -> None:
        super().__init__()
        self.configService = configService
        self.loggerService = loggerService
        self.vaultService = vaultService
        self.redisService = redisService
        self.mongooseService = mongooseService
       
        self.profiles:dict[str,Union[EmailSendInterface,_service.BaseService]] = {

        }

    def verify_dependency(self):
        ...

    def select(self,profilesId)->EmailSendInterface:
        p = self.profiles.get(profilesId,None)
        if p == None:
            raise # TODO
        if p.service_status != _service.ServiceStatus.AVAILABLE:
            raise # TODO


    def build(self,build_state=_service.DEFAULT_BUILD_STATE):
        
        ...

@_service.Service
class EmailReaderService(_service.BaseService):
    def __init__(self, configService: ConfigService,vaultService:HCVaultService,mongooseService:MongooseService) -> None:
        super().__init__()
        self.configService = configService
        self.mongooseService = mongooseService
        self.vaultService = vaultService

        self.profiles:dict[str,EmailReadInterface] = {}


    def verify_dependency(self):
        return super().verify_dependency()

    def build(self, build_state = _service.DEFAULT_BUILD_STATE):
        return super().build(build_state)

    def start_jobs(self):
        for p in self.profiles.values():
            p.start_jobs()

    
    def cancel_jobs(self):
        for p in self.profiles.values():
            p.cancel_jobs()