
from app.definition import _service
from app.services.aws_service import AmazonSESService
from app.services.config_service import ConfigService
from app.services.email.email_api_service import EmailAPIService
from app.services.email.smtp_imap_service import IMAPEmailService, SMTPEmailService
from app.utils.tools import Mock
from app.interface.email import EmailSendInterface

@_service.Service
class EmailSenderService(_service.BaseService, EmailSendInterface):
    # BUG cant resolve an abstract class
    def __init__(self, configService: ConfigService, awsSESService: AmazonSESService, smtpEmailService: SMTPEmailService,emailApiService: EmailAPIService) -> None:
        EmailSendInterface.__init__(self)
        self.configService = configService
        self.awsSESService = awsSESService
        self.smtpEmailService = smtpEmailService
        self.emailApiService = emailApiService

    def verify_dependency(self):
        ...

    def build(self):
        
        
        setattr(self,self.sendTemplateEmail.__name__,self.smtpEmailService.sendTemplateEmail)
        setattr(self,self.sendCustomEmail.__name__,self.smtpEmailService.sendCustomEmail)
        
        if False:
            setattr(self,self.sendTemplateEmail.__name__,Mock()(self.sendTemplateEmail))
            setattr(self,self.sendCustomEmail.__name__,Mock()(self.sendCustomEmail))


@_service.Service
class EmailReaderService(_service.BaseService):
    def __init__(self, configService: ConfigService, awsSESService: AmazonSESService, imapEmailService: IMAPEmailService,emailApiService: EmailAPIService) -> None:

        self.awsSESService = awsSESService
        self.imapEmailService = imapEmailService
        self.configService = configService
        self.emailApiService = emailApiService

    