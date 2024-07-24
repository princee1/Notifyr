"""
https://www.youtube.com/watch?v=W7JIdLU23GI
"""

from dataclasses import dataclass
import smtplib as smtp
import imaplib as imap
from enum import Enum
from injector import inject
from module import Module
from app.services.config import ConfigService


SMTP_NORMAL_PORT = smtp.SMTP_PORT
SMTP_SSL_PORT = smtp.SMTP_SSL_PORT
SMTP_TLS_PORT = 587


IMAP_NORMAL_PORT = 143
IMAP_SSL_TLS_PORT = 993


class EmailConnConfig():
    def setHostPort(connMode:str): pass

    def setConnFlag(mode:str): pass

    def setHostAddr(host:str): pass


class SMTPConfig(Enum,EmailConnConfig):

    GMAIL = "smtp.gmail.com"
    OUTLOOK = "smtp-mail.outlook.com"
    YAHOO = "smtp.mail.yahoo.com"

    def setHostPort(connMode: str):
        match connMode:
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
        match host:
            case str(SMTPConfig.GMAIL.name):
                return SMTPConfig.GMAIL.value
            case str(SMTPConfig.YAHOO.name):
                return SMTPConfig.YAHOO.value
            case str(SMTPConfig.OUTLOOK.name):
                return SMTPConfig.OUTLOOK.value
            case _:
                return host


class IMAPConfig (Enum,EmailConnConfig):
    """The IMAPHost class is an enumeration of the IMAP host names for the two email providers that I use
    """
    GMAIL = "imap.gmail.com"
    YAHOO = "imap.mail.yahoo.com"
    OUTLOOK = "outlook.office365.com"  # BUG potentiel : might not work

    def setHostAddr(host: str):
        match host:
            case str(IMAPConfig.GMAIL.name):
                return IMAPConfig.GMAIL.value
            case str(IMAPConfig.YAHOO.name):
                return IMAPConfig.YAHOO.value
            case str(IMAPConfig.OUTLOOK.name):
                return IMAPConfig.OUTLOOK.value
            case _:
                return  # BUG

    def setConnFlag(mode: str): return mode.lower() == "ssl"

    def setHostPort(mode: str): return IMAP_SSL_TLS_PORT if mode.lower(
    ) == "ssl" else IMAP_NORMAL_PORT


@dataclass
class Email(Module):
    hostPort: int

    def __init__(self, configService: ConfigService):
        self.configService = configService

    def build(self):
        self.connect()
        self.authenticate()

    def authenticate(self): pass

    def connect(self): pass


class EmailSender(Email):
    @inject
    def __init__(self, configService: ConfigService):
        super().__init__(configService)
        self.fromEmails: set[str] = ()
        self.tlsConn: bool = SMTPConfig.setConnFlag(
            self.configService.SMTP_EMAIL_CONN_METHOD)
        self.hostPort = SMTPConfig.setHostPort(
            self.configService.SMTP_EMAIL_CONN_METHOD) if self.configService.SMTP_EMAIL_PORT == None else self.configService.SMTP_EMAIL_PORT

    def validEmails(self):
        pass

    def build(self):
        super().build()
        self.validEmails()

    def kill(self):
        self.connector.quit()
        self.connector.close()

    def connect(self):
        try:
            self.hostAddr = SMTPConfig.setHostAddr(
                self.configService.EMAIL_HOST)
            self.connector = smtp.SMTP(self.hostAddr, self.hostPort)
            self.connector.set_debuglevel(self.configService.EMAIL_LOG_LEVEL)
        except NameError as e:
            pass  # BUG need to change the error name and a builder error
        except:
            pass

    def authenticate(self):
        try:
            if self.tlsConn:
                self.connector.ehlo()
                self.connector.starttls()
                self.connector.ehlo()
            val = self.connector.login(self.configService.EMAIL,
                                       self.configService.EMAIL_PASS)
            print(val)
            self.state = True
        except smtp.SMTPHeloError | smtp.SMTPNotSupportedError as e:
            self.state = False
            self.errorReason = e
            # TODO Throw Error build error
            pass
        except smtp.SMTPAuthenticationError as e:
            self.state = False
            self.errorReason = e
            # TODO Throw Error build error
            pass

    def sendMessage(self):
        try:
            self.connector.send_message()

        except smtp.SMTPHeloError as e:
            pass
        except smtp.SMTPRecipientsRefused as e:
            pass
        except smtp.SMTPSenderRefused as e:
            pass
        except smtp.SMTPNotSupportedError as e:
            pass
        except:
            pass


class EmailReader(Email):
    @inject
    def __init__(self, configService: ConfigService) -> None:
        super().__init__(configService)
        self.hostPort = IMAPConfig.setHostPort(
            self.configService.IMAP_EMAIL_CONN_METHOD) if self.configService.IMAP_EMAIL_PORT == None else self.configService.IMAP_EMAIL_PORT

    def build(self):
        super().build()

    def connect(self):
        self.connector = imap.IMAP4_SSL(
            host=self.configService.IMAP_EMAIL_HOST, port=self.hostPort)

    def authenticate(self):
        self.connector.login(self.configService.IMAP_EMAIL,
                             self.configService.IMAP_EMAIL_PASS)

    def kill(self):
        self.connector.logout()
        self.connector.close()
