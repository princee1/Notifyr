
import asyncio
from dataclasses import dataclass, field, fields
import functools
from random import randint
import re
import smtplib as smtp
import imaplib as imap
import poplib as pop
import socket
from typing import Callable, Iterable, Literal, Self, TypedDict

from app.interface.timers import IntervalInterface
from app.services.database_service import RedisService
from app.services.reactive_service import ReactiveService
from app.utils.prettyprint import SkipInputException
from app.classes.mail_oauth_access import OAuth, MailOAuthFactory, OAuthFlow
from app.classes.mail_provider import  SMTPConfig, IMAPConfig, MailAPI, IMAPSearchFilter
from app.utils.tools import Time

from app.utils.constant import EmailHostConstant
from app.classes.email import EmailBuilder, EmailMetadata, EmailReader, NotSameDomainEmailError

from .logger_service import LoggerService
from app.definition import _service
from .config_service import ConfigService
import ssl

from app.models.email_model import EmailTrackingORM,TrackingEmailEventORM
from app.utils.validation import email_validator

from app.utils.constant import StreamConstant
from email import message_from_bytes

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
            if not isinstance(self,BaseEmailService):
                self = self.__class__.service

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
           
            if self.type_ == 'SMTP':
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
@_service.ServiceClass
class EmailReaderService(BaseEmailService,IntervalInterface):
    service:Self # Class Singleton
    @dataclass
    class Jobs:
        job_name:str
        func:str
        args:Iterable
        kwargs:dict
        stop:bool = True
        task:asyncio.Task = None
        delay:int = field(default_factory=lambda:randint(10,100))


        async def __call__(self,):
            service: EmailReaderService = EmailReaderService.service
            callback =  getattr(service,self.func,None)
            while self.stop:
                self.is_running =True
                callback(*self.args,**self.kwargs)
                self.is_running=False
                await asyncio.sleep(self.delay)
            return 
        
        def cancel_job(self):
            self.stop=False
            return self.task.cancel()

    @dataclass
    class IMAPMailboxes:
        flags: list[str]
        delimiters: str
        name: str

        def __repr__(self):
            return f"IMAPMailboxes(flags={self.flags}, delimiters={self.delimiters}, name={self.name})"

        def __str__(self):
            return self.__repr__()

        @property
        def no_select(self)->bool:
            return "\\Noselect" in self.flags

            
        @BaseEmailService.task_lifecycle
        def rename(self, new_name: str, connector: imap.IMAP4 | imap.IMAP4_SSL):
            """Rename the mailbox."""
            status, response = connector.rename(self.name, new_name)
            if status != 'OK':
                raise imap.IMAP4.error(f"Failed to rename mailbox {self.name} to {new_name}")
            self.name = new_name
            return response

        @BaseEmailService.task_lifecycle
        def delete(self, connector: imap.IMAP4 | imap.IMAP4_SSL):
            """Delete the mailbox."""
            status, response = connector.delete(self.name)
            if status != 'OK':
                raise imap.IMAP4.error(f"Failed to delete mailbox {self.name}")
            return response

        @BaseEmailService.task_lifecycle
        def create_subfolder(self, subfolder_name: str,connector: imap.IMAP4 | imap.IMAP4_SSL):
            """Create a subfolder under the current mailbox."""
            full_name = f"{self.name}/{subfolder_name}"
            status, response = connector.create(full_name)
            if status != 'OK':
                raise imap.IMAP4.error(f"Failed to create subfolder {subfolder_name} under {self.name}")
            return full_name,response

        @BaseEmailService.task_lifecycle
        def status(self,connector: imap.IMAP4 | imap.IMAP4_SSL):
            ...

    jobs:dict[str,Jobs]={}
    
    @staticmethod
    def select_inbox(func:Callable):

        @functools.wraps(func)
        def wrapper(self:Self,inbox:str,*args,**kwargs):
            if inbox not in self.mailboxes:
                raise KeyError('Mail box not found')
            
            if self._mailboxes[inbox].no_select:
                raise imap.IMAP4.error(f'This inbox cannot be selected')
                        
            self._current_mailbox = inbox
            connector:imap.IMAP4 | imap.IMAP4_SSL = kwargs['connector']
            connector.select(inbox)
            return func(self,*args,**kwargs)

        return wrapper
    
    @staticmethod
    def register_job(job_name:str,delay:int,*args,**kwargs):
        def wrapper(func:Callable):
            func_name = func.__name__
            params = {
                'job_name':job_name,
                'func':func_name,
                'args':args,
                'kwargs':kwargs
            }
            if delay ==None or not isinstance(delay,(float,int)) or delay<=0:
                ...
            else:
                params['delay']=delay

            jobs = Self.Jobs(**params)
            if job_name in Self.jobs:
                ... # Warning 
            Self.jobs[job_name] =jobs
            return func
        return wrapper

    @staticmethod
    def cancel_job():
        for job in EmailReaderService.jobs.values():
            job.cancel_job()
        
    def __init__(self, configService: ConfigService, loggerService: LoggerService,reactiveService:ReactiveService,redisService:RedisService) -> None:
        super().__init__(configService, loggerService)
        IntervalInterface.__init__(self,True,10)
        self.reactiveService = reactiveService
        self.redisService = redisService

        self._mailboxes:dict[str,EmailReaderService.IMAPMailboxes] = {}
        self._current_mailbox:str = None

        self._init_config()
        EmailReaderService.service = self
        self._capabilities:list = None

    def _init_config(self):
        self.type_ = 'IMAP'
        self.connMethod = self.configService.IMAP_EMAIL_CONN_METHOD.lower()
        self.tlsConn: bool = IMAPConfig.setConnFlag(self.connMethod)

        self.emailHost = EmailHostConstant._member_map_[self.configService.IMAP_EMAIL_HOST]
        self.hostPort = IMAPConfig.setHostPort(
            self.configService.IMAP_EMAIL_CONN_METHOD) if self.configService.IMAP_EMAIL_PORT == None else self.configService.IMAP_EMAIL_PORT

    def _update_mailboxes(self,connector:imap.IMAP4|imap.IMAP4_SSL):
        """
            Update the mailboxes lists at each lifecycle
        """
        status, mailboxes = connector.list()
        self._mailboxes = {}
        pattern = re.compile(r'\((.*?)\) "(.*?)" "(.*?)"')
        for line in mailboxes:
            match = pattern.match(line.decode())
            if match:
                flags_str, delimiter, mailbox_name = match.groups()
                flags = flags_str.split()
                
                mailbox = self.IMAPMailboxes(flags,delimiter,mailbox_name)
                self._mailboxes[mailbox.name] = mailbox

    def _get_capabilities(self,connector:imap.IMAP4|imap.IMAP4_SSL):
        if self._capabilities !=None:
            return 

        typ, capabilities = connector.capability()
        capabilities = b' '.join(capabilities).decode().upper()
        self._capabilities = capabilities.split(' ')
        
    def authenticate(self,connector:imap.IMAP4|imap.IMAP4_SSL):
        
        try:
            if self.tlsConn:
                context = ssl.create_default_context()
                connector.starttls(context=context)
            if self.emailHost in [EmailHostConstant.ICLOUD, EmailHostConstant.GMAIL, EmailHostConstant.GMAIL_RELAY, EmailHostConstant.GMAIL_RESTRICTED] and self.configService.IMAP_PASS is not None:
                status, data = connector.login(self.configService.IMAP_EMAIL, self.configService.IMAP_PASS)
                if status != 'OK':
                    raise Exception
                
                self._update_mailboxes(connector)
                self._get_capabilities(connector)
    
                return True
            else:
                self.service_status = _service.ServiceStatus.NOT_AVAILABLE
                return False
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
    
    def read_email(self,message_ids,connector:imap.IMAP4|imap.IMAP4_SSL):

        for num in message_ids:
            status, data = connector.fetch(num, "(RFC822)")
            if status != None:
                continue
            raw_email = data[0][1]
            msg = message_from_bytes(raw_email)
            yield EmailReader(msg)
              
    def logout(self,connector:imap.IMAP4|imap.IMAP4_SSL):
        try:
            connector.close()
            connector.logout()
        except:
            ...
    
    def build(self):
        ...

    def callback(self):
        #self._temp_entry_point('INBOX')

        for job_name,job in self.jobs.items():
            #self.prettyPrinter.
            task = asyncio.create_task(job(),name=job_name)
            if job.task!=None:
                job.cancel_job()
            job.task = task
        
    def search_email(self,command:str,connector:imap.IMAP4|imap.IMAP4_SSL=None):
        status, message_numbers = connector.search(None, command)  # or "UNSEEN", "FROM someone@example.com", etc.
        if status != 'OK':
            return None
        
        return message_numbers

    def delete_email(self,message_id:str,connector:imap.IMAP4|imap.IMAP4_SSL,hard=False):
        connector.store(message_id, '+FLAGS', '\\Deleted')
        if hard:
            return connector.expunge() 
        return 
 
    def mark_as_un_seen(self,email_id:str,connector:imap.IMAP4|imap.IMAP4_SSL,seen=True):
        flag = '+' if seen else '-'
        status,result = connector.uid('STORE', email_id, f'{flag}FLAGS', '(\\Seen)')
        if status == 'OK':
            return result
        return result

    def copy_email(self,email_id:str,target_mailbox:str,connector:imap.IMAP4|imap.IMAP4_SSL,hard_delete=False):
        if target_mailbox not in self.mailboxes:
            raise imap.IMAP4.error('Target mailboxes does not exists')
        
        if connector.copy(email_id, target_mailbox)[0] != 'OK':
            return
        return self.delete_email(email_id,connector,hard_delete)
      
    @BaseEmailService.task_lifecycle
    @select_inbox
    def _temp_entry_point(self,connector:imap.IMAP4|imap.IMAP4_SSL):
        message_ids =self.search_email(IMAPSearchFilter.ALL(),connector)
        if message_ids == None:
            print('error')
            return 
        return self.read_email(message_ids,connector)
        
    @property
    def mailboxes(self):
        return self._mailboxes.keys()
    
    @property
    def capabilities(self):
        return self._capabilities

    @property
    def has_thread_capabilities(self):
        return 'THREAD=REFERENCES' in self._capabilities or 'THREAD=ORDEREDSUBJECT' in self._capabilities

# @_service.ServiceClass
class EmailAPIService(BaseEmailService):
    ...
