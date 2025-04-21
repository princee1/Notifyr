
import functools
import smtplib as smtp
import imaplib as imap
import poplib as pop
import socket
from typing import Callable, Literal

from app.interface.timers import IntervalInterface
from app.services.reactive_service import ReactiveService
from app.utils.prettyprint import SkipInputException
from app.classes.mail_oauth_access import OAuth, MailOAuthFactory, OAuthFlow
from app.classes.mail_provider import SMTPConfig, IMAPConfig, MailAPI
from app.utils.tools import Time

from .model_service import LLMModelService
from app.utils.constant import EmailHostConstant
from app.classes.email import EmailBuilder, EmailMetadata, NotSameDomainEmailError

from .logger_service import LoggerService
from app.definition import _service
from .config_service import ConfigService
import ssl

from app.utils.validation import email_validator

@_service.AbstractServiceClass
class BaseEmailService(_service.Service):
    def __init__(self, configService: ConfigService, loggerService: LoggerService):
        super().__init__()
        self.configService: ConfigService = configService
        self.loggerService: ConfigService = loggerService
        self.hostPort: int
        self.mailOAuth: OAuth = ...
        self.state = None
        self.connMethod=...
        self.last_connectionTime: float = ...
        self.emailHost: EmailHostConstant = ...
        self.type_:Literal['IMAP','SMTP']= None

    @staticmethod
    def task_lifecycle(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            self: BaseEmailService = args[0]
            connector = self.connect()
            if connector == None:
                return 
            if not self.authenticate(connector):
                return
            kwargs['connector'] = connector
            result = func(*args, **kwargs)
            self.logout(connector)
            return result
        return wrapper

    def build(self):
        if self.emailHost in [EmailHostConstant.ICLOUD, EmailHostConstant.GMAIL, EmailHostConstant.GMAIL_RELAY, EmailHostConstant.GMAIL_RESTRICTED] and self.configService.SMTP_PASS != None:
            return 
        
        params = {
            'client_id': self.configService.OAUTH_CLIENT_ID,
            'client_secret': self.configService.OAUTH_CLIENT_SECRET,
            'tenant_id': self.configService.OAUTH_OUTLOOK_TENANT_ID,
            'mail_provider': self.configService.SMTP_EMAIL_HOST
            # 'state': self.state,
        }

        self.mailOAuth = MailOAuthFactory(
            self.emailHost, params, self.configService.OAUTH_METHOD_RETRIEVER, self.configService.OAUTH_JSON_KEY_FILE)
        self.mailOAuth.load_authToken(self.configService.OAUTH_TOKEN_DATA_FILE)
        if self.mailOAuth.exists:
            try:
                if not self.mailOAuth.is_valid:
                    self.mailOAuth.refresh_access_token()
            except:
                raise _service.BuildFailureError
                
        else:
            try:
                self.mailOAuth.grant_access_token()
            except SkipInputException:
                raise _service.BuildFailureError
            
        if self.mailOAuth.access_token == None:
                raise _service.BuildFailureError

        self.service_status = _service.ServiceStatus.AVAILABLE
        self.prettyPrinter.show()

    def destroy(self):
        ...

    def authenticate(self): pass

    def connect(self):
        config:type = SMTPConfig if  self.type_ == 'SMTP' else IMAPConfig
        server_type_ssl:type = smtp.SMTP_SSL if self.type_ == 'SMTP' else imap.IMAP4_SSL
        server_type:type = smtp.SMTP if self.type_ == 'SMTP' else imap.IMAP4
        try:
            self.hostAddr = config.setHostAddr(self.configService.SMTP_EMAIL_HOST)
            if self.connMethod == 'ssl':
                connector = server_type_ssl(self.hostAddr, self.hostPort)
            else:
                connector = server_type(self.hostAddr, self.hostPort)
            connector.set_debuglevel(self.configService.SMTP_EMAIL_LOG_LEVEL)
            return connector
        except (socket.gaierror, ConnectionRefusedError, TimeoutError) as e:
            self.service_status = _service.ServiceStatus.NOT_AVAILABLE
            
        except ssl.SSLError as e:
            self.service_status = _service.ServiceStatus.NOT_AVAILABLE

        except NameError as e:
            self.service_status = _service.ServiceStatus.NOT_AVAILABLE  # BUG need to change the error name and a builder error

        return None

    def logout(self): ...

    def resetConnection(self): ...

    def help(self):
        ...


@_service.ServiceClass
class EmailSenderService(BaseEmailService):
    # BUG cant resolve an abstract class
    def __init__(self, configService: ConfigService, loggerService: LoggerService):
        super().__init__(configService, loggerService)
        self.type_ = 'SMTP'
        self.fromEmails: set[str] = set()
        self.connMethod = self.configService.SMTP_EMAIL_CONN_METHOD.lower()
        self.tlsConn: bool = SMTPConfig.setConnFlag(self.connMethod)
        self.hostPort = SMTPConfig.setHostPort(
            self.configService.SMTP_EMAIL_CONN_METHOD) if self.configService.SMTP_EMAIL_PORT == None else self.configService.SMTP_EMAIL_PORT

        self.emailHost = EmailHostConstant._member_map_[self.configService.SMTP_EMAIL_HOST]
    
    def _load_valid_from_email(self):
        config_str:str = ...
        config_str = config_str.strip()
        emails = config_str.split('|')
        emails = [email for email in emails if email_validator(email)]
        self.fromEmails.update(emails)

    def logout(self,connector:smtp.SMTP):
        try:
            connector.quit()
            connector.close()
        except:
            ...
    
    def verify_dependency(self):
        if self.configService.SMTP_EMAIL_HOST not in EmailHostConstant._member_names_:
            raise _service.BuildFailureError
        
    def authenticate(self,connector:smtp.SMTP):
        
        try:
            if self.tlsConn:
                context = ssl.create_default_context()
                connector.ehlo()
                connector.starttls(context=context)
                connector.ehlo()

            if self.emailHost in [EmailHostConstant.ICLOUD, EmailHostConstant.GMAIL, EmailHostConstant.GMAIL_RELAY, EmailHostConstant.GMAIL_RESTRICTED] and self.configService.SMTP_PASS != None:

                auth_status = connector.login(self.configService.SMTP_EMAIL, self.configService.SMTP_PASS)
            else:
                access_token = self.mailOAuth.encode_token(self.configService.SMTP_EMAIL)
                auth_status = connector.docmd("AUTH XOAUTH2", access_token)
                auth_status = tuple(auth_status)
                auth_code, auth_mess = auth_status
                if str(auth_code) != '235':
                    raise smtp.SMTPAuthenticationError(auth_code, auth_mess)
            return True
        except smtp.SMTPHeloError as e:
            self.service_status = _service.ServiceStatus.TEMPORARY_NOT_AVAILABLE
            # TODO Depends on the error code

        except smtp.SMTPNotSupportedError as e:
            self.service_status = _service.ServiceStatus.NOT_AVAILABLE

        except smtp.SMTPAuthenticationError as e:
            self.service_status = _service.ServiceStatus.NOT_AVAILABLE

        except smtp.SMTPServerDisconnected as e:
            self.service_status = _service.ServiceStatus.TEMPORARY_NOT_AVAILABLE
            # TODO Depends on the error code
        return False

    def sendTemplateEmail(self,data, meta, images):
        meta = EmailMetadata(**meta)
        email  = EmailBuilder(data,meta,images)
        return self._send_message(email)

    def sendCustomEmail(self,content, meta, images, attachment):
        meta = EmailMetadata(**meta)
        email =  EmailBuilder(content,meta,images,attachment)
        #send_custom_email(content, meta, images, attachment)
        return self._send_message(email)

    @Time
    @BaseEmailService.task_lifecycle
    def _send_message(self, email: EmailBuilder,connector:smtp.SMTP):
        try:
            emailID, message = email.mail_message
            reply_ = connector.sendmail(email.emailMetadata.From, email.emailMetadata.To, message,rcpt_options=['NOTIFY=SUCCESS,FAILURE,DELAY'])

            return {
                "emailID":emailID,
                "status":reply_
            }

        except smtp.SMTPSenderRefused as e:
            self.service_status = _service.ServiceStatus.WORKS_ALMOST_ATT
        
        except smtp.SMTPNotSupportedError as e:
            self.service_status = _service.ServiceStatus.NOT_AVAILABLE

        except smtp.SMTPServerDisconnected as e:
            print('Server disconnected')
            print(e)
            self._builded = False
            # BUG service destroyed too ?
            self.service_status = _service.ServiceStatus.TEMPORARY_NOT_AVAILABLE
            # TODO retry getting the access token
            ...

    @BaseEmailService.task_lifecycle
    def verify_same_domain_email(self,email:str,connector:smtp.SMTP):
        domain = email.split['@'][1]
        our_domain = self.configService.SMTP_EMAIL.split['@'][1]
        if our_domain != domain:
            raise NotSameDomainEmailError
        
        return connector.verify(email)

        

# @_service.ServiceClass
class EmailReaderService(BaseEmailService,IntervalInterface):
    def __init__(self, configService: ConfigService, loggerService: LoggerService, llmService: LLMModelService,reactiveService:ReactiveService) -> None:
        super().__init__(configService, loggerService)
        self.llmService=llmService
        self.reactiveService = reactiveService

        self.init()

    def init(self):
        self.type_ = 'IMAP'
        self.connMethod = self.configService.IMAP_EMAIL_CONN_METHOD.lower()
        self.tlsConn: bool = IMAPConfig.setConnFlag(self.connMethod)

        self.emailHost = EmailHostConstant._member_map_[self.configService.IMAP_EMAIL_HOST]
        self.hostPort = IMAPConfig.setHostPort(
            self.configService.IMAP_EMAIL_CONN_METHOD) if self.configService.IMAP_EMAIL_PORT == None else self.configService.IMAP_EMAIL_PORT

    def authenticate(self,connector:imap.IMAP4):
        try:
            if self.tlsConn:
                context = ssl.create_default_context()
                connector.starttls(context=context)

            if self.emailHost in [EmailHostConstant.ICLOUD, EmailHostConstant.GMAIL, EmailHostConstant.GMAIL_RELAY, EmailHostConstant.GMAIL_RESTRICTED] and self.configService.IMAP_PASS is not None:
                status, data = connector.login(self.configService.IMAP_EMAIL, self.configService.IMAP_PASS)
            else:
                self.service_status = _service.ServiceStatus.NOT_AVAILABLE
                return 
                access_token = self.mailOAuth.encode_token(self.configService.IMAP_EMAIL)
                auth_code, auth_message = connector.authenticate('AUTH XOAUTH2', access_token)
                if auth_code != 'OK':
                    raise imap.IMAP4.error(f"Authentication failed: {auth_message}")
                
        except imap.IMAP4.error as e:
            self.service_status = _service.ServiceStatus.NOT_AVAILABLE
        except imap.IMAP4.abort as e:
            self.service_status = _service.ServiceStatus.TEMPORARY_NOT_AVAILABLE
        except imap.IMAP4.readonly as e:
            self.service_status = _service.ServiceStatus.NOT_AVAILABLE
        except ssl.SSLError as e:
            self.service_status = _service.ServiceStatus.NOT_AVAILABLE
        except Exception as e:
            self.service_status = _service.ServiceStatus.NOT_AVAILABLE

# @_service.ServiceClass
class EmailAPIService(BaseEmailService):
    ...
