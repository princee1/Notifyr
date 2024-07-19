"""
https://www.youtube.com/watch?v=W7JIdLU23GI
"""

import smtplib as smtp
from enum import Enum
from injector import inject
from module import Module
from configService import ConfigService


SMTP_NORMAL_PORT = smtp.SMTP_PORT
SMTP_SSL_PORT = smtp.SMTP_SSL_PORT
SMTP_TLS_PORT = 587

class SMTPConfig(Enum):

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
            case _: ## WARNING need to add a warning
                SMTP_NORMAL_PORT

    def setConnFlag(mode: str):
        if mode.lower() == "tls":
            return True
        return False

    def setHostAddr(host: str):
        match host:
            case str(SMTPConfig.GMAIL.name):
                return SMTPConfig.GMAIL.value
            case str(SMTPConfig.YAHOO.name):
                return SMTPConfig.YAHOO.value
            case str(SMTPConfig.OUTLOOK.name):
                return SMTPConfig.OUTLOOK.value
            case _:
                raise NameError()  # BUG

class EmailSender(Module):
    @inject
    def __init__(self, configService: ConfigService):
        self.configService = configService
        self.fromEmails: set[str] = ()
        self.tlsConn: bool = SMTPConfig.setConnFlag(
            self.configService.EMAIL_CONN_METHOD)
        self.hostPort = SMTPConfig.setHostPort(
            self.configService.EMAIL_CONN_METHOD) if self.configService.EMAIL_PORT == None else self.configService.EMAIL_PORT
    
    def validEmails(self):
        pass

    def build(self):
        self.validEmails()
        self.connectSMTP()
        self.authenticate()
        
    def kill(self):
        self.connector.quit()
        self.connector.close()

    def connectSMTP(self):
        try:
            self.hostAddr = SMTPConfig.setHostAddr(self.configService.EMAIL_HOST)
            self.connector = smtp.SMTP(self.hostAddr, self.hostPort)
            self.connector.set_debuglevel(self.configService.EMAIL_LOG_LEVEL)
        except NameError as e:
            pass # BUG need to change the error name and a builder error
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

