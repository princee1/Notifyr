
from typing_extensions import Literal
from app.definition import _service
from app.services.aws_service import AmazonSESService
from app.services.config_service import ConfigService
from app.services.email.email_api_service import EmailAPIService
from app.services.email.mail_protocol_service import IMAPEmailService, SMTPEmailService
from app.utils.tools import Mock
from app.interface.email import EmailSendInterface

@_service.Service
class EmailSenderService(_service.BaseService):
    # BUG cant resolve an abstract class
    def __init__(self, configService: ConfigService, awsSESService: AmazonSESService, smtpEmailService: SMTPEmailService,emailApiService: EmailAPIService) -> None:
        super().__init__()

        self.configService = configService
        self.awsSESService = awsSESService
        self.smtpEmailService = smtpEmailService
        self.emailApiService = emailApiService

    def verify_dependency(self):
        ...

    def select(self,service:Literal['smtp','aws','api']='smtp',sender=None,conn_type:Literal['raw','oauth']=None)->EmailSendInterface:
        if service == 'smtp':
            return self.smtpEmailService
        if 'aws':
            return self.awsSESService

    def build(self,build_state=-1)
        
        ...

@_service.Service
class EmailReaderService(_service.BaseService):
    def __init__(self, configService: ConfigService, awsSESService: AmazonSESService, imapEmailService: IMAPEmailService,emailApiService: EmailAPIService) -> None:
        super().__init__()

        self.awsSESService = awsSESService
        self.imapEmailService = imapEmailService
        self.configService = configService
        self.emailApiService = emailApiService

    
    def start_jobs(self):
        self.imapEmailService.start_jobs()

    
    def cancel_jobs(self):
        self.imapEmailService.cancel_jobs()