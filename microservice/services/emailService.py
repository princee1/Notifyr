"""
https://www.youtube.com/watch?v=W7JIdLU23GI
"""

import smtplib as smtp
from enum import Enum
from injector import inject
from configService import ConfigService
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.text import MIMEBase

from __init__ import Service 



class SMTPHost(Enum):

    GMAIL = "smtp.gmail.com"
    OUTLOOK = "smtp.live.com"
    YAHOO = "smtp.mail.yahoo.com"

    def setHostPort(host: str):
        return 25 if host == SMTPHost.YAHOO else 465
    
    def setHostAddr(host):
        match host: 
            case str(SMTPHost.GMAIL.name):
                return SMTPHost.GMAIL
            case str(SMTPHost.YAHOO.name):
                return SMTPHost.YAHOO
            case str(SMTPHost.OUTLOOK.name):
                return SMTPHost.OUTLOOK
            case _:
                raise NameError() # BUG


class EmailSender(Service):

    @inject
    def __init__(self, configService: ConfigService):
        self.configService = configService
        self.hostAddr = SMTPHost.setHostAddr(self.configService.EMAIL_HOST)
        self.hostPort = SMTPHost.setHostPort(self.configService.EMAIL_PORT)
        self.connector = smtp.SMTP(self.hostAddr, self.hostPort)
        self.connector.set_debuglevel(2)
        self.fromEmails: dict[str,str] = {}
        pass

    def buildService(self):
        try: 
            self.authenticate()  
        except: 
            pass

    def authenticate(self):
        try:
            self.connector.ehlo()
            self.connector.starttls()
            self.connector.ehlo()
            self.connector.login(self.configService.EMAIL,
                                 self.configService.EMAIL_PASS)
            self.state = True
        except smtp.SMTPHeloError | smtp.SMTPNotSupportedError:
            self.state = False
            pass
        except smtp.SMTPAuthenticationError as e:
            self.state = False
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

    def addFromEmail(self,name,email):
        self.fromEmails[name] = email
        return self
        
    
class MessageBuilder():

    def __init__(self, subject, sender, ) -> None:
        self.mail = MIMEMultipart()
        pass

    def attach(self):
        return self
    
    def  build(self):
        pass
    pass
    
   
