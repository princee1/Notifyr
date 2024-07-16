"""
https://www.youtube.com/watch?v=W7JIdLU23GI
"""

import smtplib as smtp
from enum import Enum
from injector import inject
from configService import ConfigService
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from __init__ import Service

SMTP_NORMAL_PORT = smtp.SMTP_PORT
SMTP_SSL_PORT = smtp.SMTP_SSL_PORT
SMTP_TLS_PORT = 587


class SMTPHost(Enum):

    GMAIL = "smtp.gmail.com"
    OUTLOOK = "smtp-mail.outlook.com"
    YAHOO = "smtp.mail.yahoo.com"

    def setHostPort(connMode: str):
        match connMode:
            case "tls":
                return SMTP_TLS_PORT
            case "ssl":
                return SMTP_SSL_PORT
            case _:
                return SMTP_NORMAL_PORT

    def setConnFlag(mode: str):
        if mode.lower() == "tls":
            return True
        return False

    def setHostAddr(host: str):
        match host:
            case str(SMTPHost.GMAIL.name):
                return SMTPHost.GMAIL.value
            case str(SMTPHost.YAHOO.name):
                return SMTPHost.YAHOO.value
            case str(SMTPHost.OUTLOOK.name):
                return SMTPHost.OUTLOOK.value
            case _:
                raise NameError()  # BUG


class EmailSender(Service):

    @inject
    def __init__(self, configService: ConfigService):
        self.configService = configService
        self.hostAddr = SMTPHost.setHostAddr(self.configService.EMAIL_HOST)
        self.tlsConn: bool = SMTPHost.setConnFlag(
            self.configService.EMAIL_CONN_METHOD)
        self.hostPort = SMTPHost.setHostPort(
            self.configService.EMAIL_CONN_METHOD) if self.configService.EMAIL_PORT == None else self.configService.EMAIL_PORT
        print(self.hostPort)
        self.connector = smtp.SMTP(self.hostAddr, self.hostPort)
        self.connector.set_debuglevel(self.configService.EMAIL_LOG_LEVEL)
        self.fromEmails: dict[str, str] = {}
        pass

    def buildService(self):
        try:
            self.authenticate()
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

            pass
        except smtp.SMTPAuthenticationError as e:
            self.state = False
            self.errorReason = e
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

    def addFromEmail(self, name, email):
        self.fromEmails[name] = email
        return self


class MessageBuilder():

    def __init__(self, subject, sender, ) -> None:
        self.mail = MIMEMultipart()
        pass

    def attach(self):
        return self

    def build(self):
        pass
    pass
