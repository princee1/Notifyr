
import functools
import smtplib as smtp
import imaplib as imap
import poplib as pop
from typing import Callable

from utils.fileIO import JSONFile
from utils.prettyprint import SkipInputException
from classes.mail_oauth_access import OAuth, MailOAuthFactory, OAuthFlow
from classes.mail_provider import SMTPConfig, IMAPConfig, MailAPI

from .model_service import LLMModelService
from utils.constant import EmailHostConstant
from classes.email import EmailBuilder
from interface.threads import ThreadInterface
from interface.timers import SchedulerInterface

from .logger_service import LoggerService
from definition import _service
from .config_service import ConfigService
import ssl


@_service.AbstractServiceClass
class BaseEmailService(_service.Service):
    def __init__(self, configService: ConfigService, loggerService: LoggerService):
        super().__init__()
        self.configService: ConfigService = configService
        self.loggerService: ConfigService = loggerService
        self.hostPort: int
        self.mailOAuth: OAuth = ...
        self.state = None
        self.last_connectionTime:float =...
        self.emailHost:EmailHostConstant =...

    @staticmethod
    def task_lifecycle(func:Callable):
        @functools.warps(func)
        def wrapper(*args,**kwargs):
            self:BaseEmailService = args[0]
            self.connect()
            self.authenticate()
            result = func(*args,**kwargs)
            self.logout()
            return result
        return wrapper

    def build(self):
        params = {
            'client_id': self.configService.OAUTH_CLIENT_ID,
            'client_secret': self.configService.OAUTH_CLIENT_SECRET,
            'tenant_id': self.configService.OAUTH_OUTLOOK_TENANT_ID,
            #'state': self.state,
        }
        self.mailOAuth = MailOAuthFactory(
            self.emailHost, params, self.configService.OAUTH_METHOD_RETRIEVER, self.configService.OAUTH_JSON_KEY_FILE)
        self.mailOAuth.load_authToken(self.configService.OAUTH_TOKEN_DATA_FILE)
        if self.mailOAuth.exists:

            try:
                if not self.mailOAuth.is_valid:
                    self.mailOAuth.refresh_access_token()
            except:
                ...
        else:
            try:
                self.mailOAuth.grant_access_token() 
            except SkipInputException:
                raise _service.BuildFailureError

        self.connect()
        self.authenticate()
        self.prettyPrinter.show()

    def destroy(self):
        self.logout()

    def authenticate(self): pass

    def connect(self): pass

    def logout(self): ...

    def resetConnection(self): ...

    def help(self):
        ...


@_service.ServiceClass
class EmailSenderService(BaseEmailService):
    # BUG cant resolve an abstract class
    def __init__(self, configService: ConfigService, loggerService: LoggerService):
        super().__init__(configService, loggerService)
        self.fromEmails: set[str] = ()
        self.tlsConn: bool = SMTPConfig.setConnFlag(
            self.configService.SMTP_EMAIL_CONN_METHOD)
        self.hostPort = SMTPConfig.setHostPort(
            self.configService.SMTP_EMAIL_CONN_METHOD) if self.configService.SMTP_EMAIL_PORT == None else self.configService.SMTP_EMAIL_PORT
        self.emailHost = EmailHostConstant._member_map_[self.configService.SMTP_EMAIL_HOST]

    def logout(self):
        self.connector.quit()
        self.connector.close()
        
    def expn(self, addresses: str):
        return self.connector.expn(addresses)

    def connect(self):
        try:
            self.hostAddr = SMTPConfig.setHostAddr(
                self.configService.SMTP_EMAIL_HOST)
            self.connector = smtp.SMTP(self.hostAddr, self.hostPort)
            self.connector.set_debuglevel(
                self.configService.SMTP_EMAIL_LOG_LEVEL)
        except NameError as e:
            pass  # BUG need to change the error name and a builder error
        except:
            pass

    def sendAutomaticMessage(self): pass

    def authenticate(self):
        try:
            if self.tlsConn:
                context = ssl.create_default_context()
                self.connector.ehlo()
                self.connector.starttls(context=context)
                self.connector.ehlo()

            if EmailHostConstant._member_map_[self.configService.SMTP_EMAIL_HOST] == EmailHostConstant.ICLOUD:

                auth_status=self.connector.login(self.configService.SMTP_EMAIL,self.configService.SMTP_PASS)
            else:
                if self.mailOAuth.access_token ==None:
                    raise ...
                access_token = self.mailOAuth.encode_token(self.configService.SMTP_EMAIL)
                auth_status = self.connector.docmd("AUTH XOAUTH2", access_token)
                print(auth_status)
                self.prettyPrinter.wait(1,True)
            self.state = True
            self._builded = True  # BUG
        except smtp.SMTPHeloError as e:
            pass
        except smtp.SMTPNotSupportedError as e:
            ...
        except smtp.SMTPAuthenticationError as e:
            ...
        except smtp.SMTPServerDisconnected as e:
            ...

    def send_message(self, email: EmailBuilder):
        try:
            if not self._builded:
                raise _service.ServiceNotAvailableError
            
            emailID, message = email.mail_message
            for to in email.emailMetadata.To:
                self.connector.verify(to)
            self.connector.sendmail(
                email.emailMetadata.From, email.emailMetadata.To, message)
            self.prettyPrinter.success(
                'Mail sent successfully', saveable=False)
        except smtp.SMTPHeloError as e:
            pass
        except smtp.SMTPRecipientsRefused as e:
            pass
        except smtp.SMTPSenderRefused as e:
            pass
        except smtp.SMTPNotSupportedError as e:
            pass
        except smtp.SMTPDataError as e:
            pass
        except smtp.SMTPServerDisconnected as e:
            ...


#@_service.ServiceClass
class EmailReaderService(BaseEmailService):
    def __init__(self, configService: ConfigService, loggerService: LoggerService, trainingService: LLMModelService,) -> None:
        super().__init__(configService, loggerService)
        self.hostPort = IMAPConfig.setHostPort(
            self.configService.IMAP_EMAIL_CONN_METHOD) if self.configService.IMAP_EMAIL_PORT == None else self.configService.IMAP_EMAIL_PORT

    def build(self):
        ...
    def connect(self):
        self.connector = imap.IMAP4_SSL(
            host=self.configService.IMAP_EMAIL_HOST, port=self.hostPort)

    def authenticate(self):
        self.connector.login(self.configService.IMAP_EMAIL,
                             self.configService.IMAP_EMAIL_PASS)
    def destroy(self):
        self.connector.logout()
        self.connector.close()

    def readEmail(self):
        pass

    def recurrenceReading():
        pass

    def updateRecurrenceReading(self):
        pass


#@_service.ServiceClass
class EmailAPIService(BaseEmailService):
    ...
