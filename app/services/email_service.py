
import smtplib as smtp
import imaplib as imap
import poplib as pop

from enum import Enum
from typing import Literal

from .training_service import TrainingService
from classes.email import EmailBuilder
from interface.threads import ThreadInterface
from interface.timers import SchedulerInterface

from .logger_service import LoggerService
from definition import _service
from .config_service import ConfigService
import ssl

SMTP_NORMAL_PORT = smtp.SMTP_PORT
SMTP_SSL_PORT = smtp.SMTP_SSL_PORT
SMTP_TLS_PORT = 587


IMAP_NORMAL_PORT = 143
IMAP_SSL_TLS_PORT = 993

ConnMode = Literal['tls','ssl','normal']

class EmailConnInterface():
    def setHostPort(connMode: str): pass

    def setConnFlag(mode: str): pass

    def setHostAddr(host: str): pass


class SMTPConfig(EmailConnInterface, Enum):

    GMAIL_RELAY = "smtp-relay.gmail.com"
    GMAIL = "smtp.gmail.com"
    OUTLOOK = "smtp.office365.com"
    YAHOO = "smtp.mail.yahoo.com"

    def setHostPort(connMode: ConnMode | str):
        match connMode.lower().strip():
            case "tls":
                return SMTP_TLS_PORT
            case "ssl":
                return SMTP_SSL_PORT
            case "normal":
                return SMTP_NORMAL_PORT
            case _:  # WARNING need to add a warning
                SMTP_NORMAL_PORT

    def setConnFlag(mode: str): return mode.lower() == "tls"

    def setHostAddr(host: str):
        match host.upper().strip():
            case str(SMTPConfig.GMAIL.name):
                return SMTPConfig.GMAIL.value
            case str(SMTPConfig.YAHOO.name):
                return SMTPConfig.YAHOO.value
            case str(SMTPConfig.OUTLOOK.name):
                return SMTPConfig.OUTLOOK.value
            case _:
                return host


class IMAPConfig (EmailConnInterface, Enum):
    """The IMAPHost class is an enumeration of the IMAP host names for the two email providers that I use
    """
    GMAIL = "imap.gmail.com"
    YAHOO = "imap.mail.yahoo.com"
    OUTLOOK = "outlook.office365.com"  # BUG potentiel : might not work

    def setHostAddr(host: str):
        match host.upper().strip():
            case str(IMAPConfig.GMAIL.name):
                return IMAPConfig.GMAIL.value
            case str(IMAPConfig.YAHOO.name):
                return IMAPConfig.YAHOO.value
            case str(IMAPConfig.OUTLOOK.name):
                return IMAPConfig.OUTLOOK.value
            case _:
                return  # BUG

    def setConnFlag(mode: str): return mode.lower() == "ssl"

    def setHostPort(mode: str): return IMAP_SSL_TLS_PORT if mode.lower().strip() == "ssl" else IMAP_NORMAL_PORT


@_service.AbstractServiceClass
class EmailService(_service.Service):
    def __init__(self, configService: ConfigService, loggerService: LoggerService):
        super().__init__()
        self.configService = configService
        self.loggerService = loggerService
        self.hostPort: int

    def build(self):
        self.connect()
        self.authenticate()

    def authenticate(self): pass

    def connect(self): pass

    def logout(self):...

    def resetConnection(self): ...

    def help(self):
        ...

@_service.ServiceClass
class EmailSenderService(EmailService):
    # BUG cant resolve an abstract class
    def __init__(self, configService: ConfigService, loggerService: LoggerService):
        super().__init__(configService, loggerService)
        self.fromEmails: set[str] = ()
        self.tlsConn: bool = SMTPConfig.setConnFlag(self.configService.SMTP_EMAIL_CONN_METHOD)
        self.hostPort = SMTPConfig.setHostPort(self.configService.SMTP_EMAIL_CONN_METHOD) if self.configService.SMTP_EMAIL_PORT == None else self.configService.SMTP_EMAIL_PORT

    def validEmails(self):
        pass

    def build(self):
        super().build()
        self.validEmails()

    def destroy(self):
        self.connector.quit()
        self.connector.close()

    def expn(self,addresses:str):
        return self.connector.expn(addresses)

    def connect(self):
        try:
            self.hostAddr = SMTPConfig.setHostAddr(self.configService.SMTP_EMAIL_HOST)
            self.connector = smtp.SMTP(self.hostAddr, self.hostPort)
            self.connector.set_debuglevel(self.configService.SMTP_EMAIL_LOG_LEVEL)
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
            
            #val = self.connector.login(self.configService.SMTP_EMAIL,self.configService.SMTP_PASS)

            self.connector.docmd("AUTH",f'XOAUTH2 {...}')
            self.state = True
            self._builded = True # BUG
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
            self._builded = True # BUG 
            if not self._builded :
                raise _service.ServiceNotAvailableError
            emailID,message=email.mail_message
            for to in email.emailMetadata.To:
                self.connector.verify(to)
            self.connector.sendmail(email.emailMetadata.From, email.emailMetadata.To,message)
            self.prettyPrinter.success('Mail sent successfully',saveable =False)
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

@_service.ServiceClass
class EmailReaderService(EmailService):
    def __init__(self, configService: ConfigService, loggerService: LoggerService,trainingService:TrainingService,) -> None:
        super().__init__(configService, loggerService)
        self.hostPort = IMAPConfig.setHostPort(
            self.configService.IMAP_EMAIL_CONN_METHOD) if self.configService.IMAP_EMAIL_PORT == None else self.configService.IMAP_EMAIL_PORT

    def build(self):
        # super().build()
        # TODO IMAP connection
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
