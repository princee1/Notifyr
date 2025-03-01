
import functools
import smtplib as smtp
import imaplib as imap
import poplib as pop
import socket
from typing import Callable

from app.utils.prettyprint import SkipInputException
from app.classes.mail_oauth_access import OAuth, MailOAuthFactory, OAuthFlow
from app.classes.mail_provider import SMTPConfig, IMAPConfig, MailAPI

from .model_service import LLMModelService
from app.utils.constant import EmailHostConstant
from app.classes.email import EmailBuilder, EmailMetadata

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
        self.last_connectionTime: float = ...
        self.emailHost: EmailHostConstant = ...

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
            kwargs['connector'] = connector # BUG if the name changes it will not work
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

    def connect(self):
        try:
            self.hostAddr = SMTPConfig.setHostAddr(
                self.configService.SMTP_EMAIL_HOST)
            if self.connMethod == 'ssl':
                connector = smtp.SMTP_SSL(self.hostAddr, self.hostPort)
            else:
                connector = smtp.SMTP(self.hostAddr, self.hostPort)
            connector.set_debuglevel(
                self.configService.SMTP_EMAIL_LOG_LEVEL)
            return connector
        except (socket.gaierror, ConnectionRefusedError, TimeoutError) as e:
            self.service_status = _service.ServiceStatus.NOT_AVAILABLE
            
        except ssl.SSLError as e:
            self.service_status = _service.ServiceStatus.NOT_AVAILABLE

        except NameError as e:
            self.service_status = _service.ServiceStatus.NOT_AVAILABLE  # BUG need to change the error name and a builder error

        return None

    def verify_dependency(self):
        if self.configService.SMTP_EMAIL_HOST not in EmailHostConstant._member_names_:
            raise _service.BuildFailureError
        


    def sendAutomaticMessage(self): pass

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

    @BaseEmailService.task_lifecycle
    def _send_message(self, email: EmailBuilder,connector:smtp.SMTP):
        try:
            emailID, message = email.mail_message
            reply_ = connector.sendmail(email.emailMetadata.From, email.emailMetadata.To, message)

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

    
# @_service.ServiceClass
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


# @_service.ServiceClass
class EmailAPIService(BaseEmailService):
    ...


class EmailDnsService(_service.Service):
    ...