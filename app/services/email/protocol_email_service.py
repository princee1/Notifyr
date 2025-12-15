
from dataclasses import dataclass
from datetime import datetime, timezone
import functools
import re
import smtplib as smtp
import imaplib as imap
import socket
from typing import Callable, Literal, Self

from bs4 import BeautifulSoup

from app.classes.profiles import ProfileState,ProfileModelException
from app.errors.service_error import BuildFailureError, BuildWarningError
from app.models.communication_model import IMAPProfileModel, ProtocolProfileModel, SMTPProfileModel
from app.services.database_service import MongooseService, RedisService
from app.services.profile_service import ProfileMiniService
from app.services.reactive_service import ReactiveService
from app.utils.helper import get_value_in_list, uuid_v1_mc
from app.utils.prettyprint import SkipInputException
#from app.classes.mail_oauth_access import OAuth, MailOAuthFactory
from app.classes.mail_provider import IMAPCriteriaBuilder, SMTPConfig, IMAPConfig, IMAPSearchFilter as Search, SMTPErrorCode, get_email_provider_name, get_error_description
from app.utils.tools import Time,Mock

from app.utils.constant import EmailHostConstant
from app.classes.email import EmailBuilder, EmailMetadata, EmailReader, NotSameDomainEmailError, extract_email_id_from_msgid

from ..logger_service import LoggerService
from app.definition import _service
from ..config_service import CeleryMode, ConfigService
import ssl

from app.models.email_model import EmailStatus, EmailTrackingORM, TrackingEmailEventORM, map_smtp_error_to_status

from app.utils.constant import StreamConstant
from email import message_from_bytes
from app.interface.profile_event import ProfileEventInterface
from app.interface.email import EmailInterface, EmailReadInterface, EmailSendInterface



class BaseEmailService(_service.BaseMiniService, ProfileEventInterface):

    def __init__(self, configService: ConfigService, loggerService: LoggerService, redisService: RedisService,profileMiniService:ProfileMiniService[ProtocolProfileModel]):
        self.depService = profileMiniService
        super().__init__(depService=profileMiniService,id=None)
        self.configService: ConfigService = configService
        self.loggerService: LoggerService = loggerService
        ProfileEventInterface.__init__(self, redisService)

        self.hostPort: int
        #self.mailOAuth: OAuth = ...
        self.state = None
        self.connMethod = ...
        self.last_connectionTime: float = ...
        self.emailHost: EmailHostConstant = ...
       
        self.log_level:int = None

        self.auth_method:Literal['password','oauth'] = ...
        self.type_: Literal['IMAP', 'SMTP'] = None
    
    @staticmethod
    def Lifecycle(pref: Literal['async', 'sync'] = None,build:bool =False):

        if ConfigService._celery_env != CeleryMode.none:
            pref = 'sync'
        elif pref == None:
            pref = 'async'
        else:
            ...
        
        def decorator(func:Callable):

            @_service.BaseMiniService.DynamicTaskContext(pref)
            @functools.wraps(func)
            def wrapper(*args,**kwargs):
                self: Self = args[0]
                connector = self.connect(build)
                if connector == None:
                    return

                if not self.authenticate(connector,build):
                    return
            
                kwargs['connector'] = connector
                result = func(*args, **kwargs)
                self.logout(connector,build)
                return result

            return wrapper

        return decorator

    def init_protocol_config(self):
        config: type[SMTPConfig |IMAPConfig] = SMTPConfig if self.type_ == 'SMTP' else IMAPConfig

        self.connMethod = self.depService.model.conn_method.lower()
        self.tlsConn: bool = config.setConnFlag(self.connMethod)
        self.emailHost = self.depService.model.email_host

        if self.emailHost == EmailHostConstant.CUSTOM:
            self.hostPort = self.depService.model.port
            self.hostAddr = self.depService.model.server
            if self.hostPort == None or self.hostAddr == None:
                raise BuildFailureError('Missing connection value Port: {self.hostPort}, Addr: {self.hostAddr}')
        else:
            self.hostPort = config.setHostPort(self.connMethod) if self.depService.model.port == None else self.depService.model.port
            self.hostAddr = config.setHostAddr(self.emailHost)

    def build(self,build_state=-1):
        self.init_protocol_config()

    def destroy(self,destroy_state=-1):
        ...

    def authenticate(self): 
        pass

    def connect(self,build:bool):
        server_type_ssl: type = smtp.SMTP_SSL if self.type_ == 'SMTP' else imap.IMAP4_SSL
        server_type: type = smtp.SMTP if self.type_ == 'SMTP' else imap.IMAP4

        try:
            if self.connMethod == 'ssl':
                connector = server_type_ssl(self.hostAddr, self.hostPort)
            else:
                connector = server_type(self.hostAddr, self.hostPort)

            if self.type_ == 'SMTP':
                connector.set_debuglevel(self.log_level)
            return connector
        except (socket.gaierror, ConnectionRefusedError, TimeoutError) as e:
            if build:
                raise BuildFailureError

        except ssl.SSLError as e:
            if build:
                raise BuildFailureError

        except NameError as e:
            # BUG need to change the error name and a builder error
            if build:
                raise BuildFailureError

        return None

    def logout(self): 
        ...

    @Lifecycle('sync',build=True)
    def verify_connection(self,connector = None):
        ...

    def verify_dependency(self):
        if self.depService.model.profile_state != ProfileState.ACTIVE:
            raise _service.BuildFailureError(f'Profile is not active {self.depService.model.profile_state.name} ')

    async def async_verify_dependency(self):
        async with self.depService.statusLock.reader:
            self.verify_dependency()
            return True

@_service.MiniService(
    override_init=True,
    links=[_service.LinkDep(ProfileMiniService,to_build=True,to_destroy=True)]
)
class SMTPEmailMiniService(BaseEmailService,EmailSendInterface):

    SMTP_LOG_LEVEL = 0
    # BUG cant resolve an abstract class
    def __init__(self,profileMiniService:ProfileMiniService[SMTPProfileModel], configService: ConfigService, loggerService: LoggerService, redisService: RedisService):
        self.depService = profileMiniService
        BaseEmailService.__init__(self,configService, loggerService, redisService,profileMiniService)
        EmailSendInterface.__init__(self,self.depService.model.email_address,self.depService.model.disposition_notification_to,self.depService.model.return_receipt_to)
        self.type_ = 'SMTP'
        self.log_level = self.SMTP_LOG_LEVEL
        
    def logout(self, connector: smtp.SMTP,build:bool):
        try:
            connector.quit()
            connector.close()
        except:
            ...

    def verify_dependency(self):
        ...

    def oauth_connect(self):
        return
        params = {
            'client_id': self.configService.OAUTH_CLIENT_ID,
            'client_secret': self.configService.OAUTH_CLIENT_SECRET,
            'tenant_id': self.configService.OAUTH_OUTLOOK_TENANT_ID,
            'mail_provider': self.email_address
            # 'state': self.state,
        }

        self.mailOAuth = MailOAuthFactory(self.emailHost, params, self.configService.OAUTH_METHOD_RETRIEVER, self.configService.OAUTH_JSON_KEY_FILE)
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

    def authenticate(self, connector: smtp.SMTP,build:bool):

        try:
            if self.tlsConn:
                context = ssl.create_default_context()
                connector.ehlo()
                connector.starttls(context=context)
                connector.ehlo()
            
            if self.auth_method == 'password':
                auth_status = connector.login(self.email_address, self.depService.credentials.to_plain()['password'])
            else:
                access_token = self.mailOAuth.encode_token(self.email_address)
                auth_status = connector.docmd("AUTH XOAUTH2", access_token)
                auth_status = tuple(auth_status)
                auth_code, auth_mess = auth_status
                if str(auth_code) != '235':
                    raise smtp.SMTPAuthenticationError(auth_code, auth_mess)
            return True
        except smtp.SMTPHeloError as e:
            if build:
                raise BuildWarningError
                # TODO Depends on the error code

        except smtp.SMTPNotSupportedError as e:
            if build:
                raise BuildFailureError

        except smtp.SMTPAuthenticationError as e:
            if build:
                raise BuildFailureError

        except smtp.SMTPServerDisconnected as e:
            if build:
                raise BuildWarningError
            # TODO Depends on the error code
        return False

    def build(self, build_state=-1):
        self.auth_method = self.depService.model.auth_mode
        super().build(build_state)
        if self.auth_method == 'oauth':
            self.oauth_connect()

        self.verify_connection()

    @Mock()
    @ProfileEventInterface.EventWrapper
    @BaseEmailService.Lifecycle('async')
    def sendTemplateEmail(self, data, meta, images,contact_id=None,profile:str=None, connector: smtp.SMTP = None,):
        meta = EmailMetadata(**meta)
        email = EmailBuilder(data, meta, images)
        return self._send_message(email, contact_ids=contact_id, connector=connector)

    @Mock()
    @ProfileEventInterface.EventWrapper
    @BaseEmailService.Lifecycle('async')
    def sendCustomEmail(self, content, meta, images, attachment,contact_id=None,profile:str=None, connector: smtp.SMTP = None):
        meta = EmailMetadata(**meta)
        email = EmailBuilder(content, meta, images, attachment)
        return self._send_message(email, contact_ids=contact_id, connector=connector)

    @BaseEmailService.Lifecycle('async')
    def reply_to_an_email(self, content, meta, images, attachment, reply_to, references, connector: smtp.SMTP = None, contact_ids:list[str]=None):
        meta = EmailMetadata(**meta)
        email = EmailBuilder(content, meta, images, attachment)
        # TODO add references and reply_to

        # if self.configService.celery_env == CeleryMode.none:
        #     return await self._send_message(email, message_tracking_id, contact_id=contact_id)
        return self._send_message(email,contact_ids=contact_ids, connector=connector)

    def _send_message(self, email: EmailBuilder, connector: smtp.SMTP, contact_ids:list[ str] = []):
        replies = []
        events = []
        for i,(emailID, message) in enumerate(email.create_for_recipient()):

            try:
                event_id = str(uuid_v1_mc())
                now = datetime.now(timezone.utc).isoformat()
                reply_ = None
                reply_ = connector.sendmail(email.emailMetadata.From, email.To[i], message, rcpt_options=['NOTIFY=SUCCESS,FAILURE,DELAY'])
                email_status = EmailStatus.SENT.value
                description = "Email successfully sent."

            except smtp.SMTPRecipientsRefused as e:
                email_status = EmailStatus.BLOCKED.value
                description = "Email blocked due to recipient refusal."
            
            except smtp.SMTPDataError as e:
                email_status = EmailStatus.FAILED.value
                description = "Email failed due to error in the message"

            except smtp.SMTPSenderRefused as e:
                self.service_status = _service.ServiceStatus.WORKS_ALMOST_ATT
                email_status = EmailStatus.FAILED.value
                description = "Email failed due to sender refusal."

            except smtp.SMTPNotSupportedError as e:
                raise BuildFailureError
                email_status = EmailStatus.FAILED.value
                description = "Email failed due to unsupported SMTP operation."

            except smtp.SMTPServerDisconnected as e:
                email_status = EmailStatus.FAILED.value
                description = "Email failed due to server disconnection."

                print('Server disconnected')
                print(e)
                self._builded = False
                self.service_status = _service.ServiceStatus.TEMPORARY_NOT_AVAILABLE

            finally:
                if get_value_in_list(email.emailMetadata._X_Email_ID,i):
                    event = TrackingEmailEventORM.JSON(
                        description=description,
                        event_id=event_id,
                        email_id=email.emailMetadata._X_Email_ID[i],
                        #contact_id=contact_ids[i] if i in contact_ids else  None,
                        current_event=email_status,
                        date_event_received=now,
                        # VERIFY if To is a list then put it in the for loop
                        esp_provider=get_email_provider_name(email.emailMetadata.To[i]))
                    events.append(event)

                replies.append( {"emailID": emailID,"status": reply_})

        return replies, (StreamConstant.EMAIL_EVENT_STREAM, events), {}

    @BaseEmailService.Lifecycle()
    def verify_same_domain_email(self, email: str, connector: smtp.SMTP):
        domain = email.split['@'][1]
        our_domain = self.email_address.split['@'][1]
        if our_domain != domain:
            raise NotSameDomainEmailError

        return (connector.verify(email),)
            

@_service.MiniService(
    override_init=True,
    links=[_service.LinkDep(ProfileMiniService,to_build=True,to_destroy=True)]
    )
class IMAPEmailMiniService(BaseEmailService,EmailReadInterface):

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
        def no_select(self) -> bool:
            return "\\Noselect" in self.flags

        def rename(self, new_name: str, connector: imap.IMAP4 | imap.IMAP4_SSL):
            """Rename the mailbox."""
            status, response = connector.rename(self.name, new_name)
            if status != 'OK':
                raise imap.IMAP4.error(
                    f"Failed to rename mailbox {self.name} to {new_name}")
            self.name = new_name
            return (response,)

        def delete(self, connector: imap.IMAP4 | imap.IMAP4_SSL):
            """Delete the mailbox."""
            status, response = connector.delete(self.name)
            if status != 'OK':
                raise imap.IMAP4.error(f"Failed to delete mailbox {self.name}")
            return (response,)

        def create_subfolder(self, subfolder_name: str, connector: imap.IMAP4 | imap.IMAP4_SSL):
            """Create a subfolder under the current mailbox."""
            full_name = f"{self.name}/{subfolder_name}"
            status, response = connector.create(full_name)
            if status != 'OK':
                raise imap.IMAP4.error(
                    f"Failed to create subfolder {subfolder_name} under {self.name}")
            return ((full_name, response),)

        def status(self, connector: imap.IMAP4 | imap.IMAP4_SSL):
            ...

    @staticmethod
    def select_inbox(func: Callable):

        def callback(self: Self, inbox: str, kwargs):
            if inbox not in self.mailboxes:
                raise KeyError('Mail box not found')

            if self._mailboxes[inbox].no_select:
                raise imap.IMAP4.error(f'This inbox cannot be selected')

            connector: imap.IMAP4 | imap.IMAP4_SSL = kwargs['connector']
            connector.select(inbox)

        @functools.wraps(func)
        def wrapper(self: Self, inbox: str, *args, **kwargs):
            callback(self, inbox, kwargs)
            return func(self, *args, **kwargs)
        
        return wrapper

    def __init__(self,profileMiniService:ProfileMiniService[IMAPProfileModel], configService: ConfigService, loggerService: LoggerService, reactiveService: ReactiveService, redisService: RedisService) -> None:
        self.depService = profileMiniService
        BaseEmailService.__init__(self,configService, loggerService, redisService,profileMiniService)
        EmailReadInterface.__init__(self,self.depService.model.email_address,None)
        self.reactiveService = reactiveService
        self.redisService = redisService
        self.type_ = 'IMAP'

        self._mailboxes: dict[str, IMAPEmailMiniService.IMAPMailboxes] = {}
        self._capabilities: list = None
        self.auth_method = 'password'

    def _update_mailboxes(self, connector: imap.IMAP4 | imap.IMAP4_SSL):
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

                mailbox = self.IMAPMailboxes(flags, delimiter, mailbox_name)
                self._mailboxes[mailbox.name] = mailbox

    def _get_capabilities(self, connector: imap.IMAP4 | imap.IMAP4_SSL):
        if self._capabilities != None:
            return

        typ, capabilities = connector.capability()
        capabilities = b' '.join(capabilities).decode().upper()
        self._capabilities = capabilities.split(' ')

    def authenticate(self, connector: imap.IMAP4 | imap.IMAP4_SSL,build:bool):

        try:
            if self.tlsConn:
                context = ssl.create_default_context()
                connector.starttls(context=context)
            
            status, data = connector.login(self.email_address, self.depService.credentials.to_plain()['password'])
            
            if status != 'OK':
                raise Exception

            self._update_mailboxes(connector)
            self._get_capabilities(connector)

            return True
            
        except imap.IMAP4.error as e:
            if build:
                raise BuildFailureError
        except imap.IMAP4.abort as e:
            if build:
                raise BuildWarningError
        except imap.IMAP4.readonly as e:
            if build:
                raise BuildFailureError
        except ssl.SSLError as e:
            if build:
                raise BuildFailureError
        except Exception as e:
            if build:
                raise BuildFailureError

    def read_email(self, message_ids, connector: imap.IMAP4 | imap.IMAP4_SSL, max_count: int = None):
        for num in message_ids[:max_count]:
            status, data = connector.fetch(num, "(RFC822)")
            if status != 'OK':
                continue
            raw_email = data[0][1]
            msg = message_from_bytes(raw_email)
            yield EmailReader(msg)

    def logout(self, connector: imap.IMAP4 | imap.IMAP4_SSL,build:bool):
        try:
            connector.close()
            connector.logout()
        except:
            ...

    def search_email(self, *command: str, connector: imap.IMAP4 | imap.IMAP4_SSL = None):
        # or "UNSEEN", "FROM someone@example.com", etc.
        status, message_numbers = connector.search(None, *command)
        if status != 'OK':
            return []

        return message_numbers[0].decode().split()

    def delete_email(self, message_id: str, connector: imap.IMAP4 | imap.IMAP4_SSL, hard=False):
        connector.store(message_id, '+FLAGS', '\\Deleted')
        if hard:
            return connector.expunge()
        return

    def mark_as_un_seen(self, email_id: str, connector: imap.IMAP4 | imap.IMAP4_SSL, seen=True):
        flag = '+' if seen else '-'
        status, result = connector.uid(
            'STORE', email_id, f'{flag}FLAGS', '(\\Seen)')
        if status == 'OK':
            return result
        return result

    def copy_email(self, email_id: str, target_mailbox: str, connector: imap.IMAP4 | imap.IMAP4_SSL, hard_delete=False):
        if target_mailbox not in self.mailboxes:
            raise imap.IMAP4.error('Target mailboxes does not exists')

        if connector.copy(email_id, target_mailbox)[0] != 'OK':
            return
        return self.delete_email(email_id, connector, hard_delete)

    def build(self, build_state=-1):
        super().build(build_state)
        self.verify_connection()

    #@EmailReadInterface.register_job('Parse DNS Email',(60,180),'INBOX', None)
    @ProfileEventInterface.EventWrapper
    @BaseEmailService.Lifecycle('async')
    @select_inbox
    def parse_dns_email(self, max_count, connector: imap.IMAP4 | imap.IMAP4_SSL):
        criteria = IMAPCriteriaBuilder()
        criteria.add(Search.UNSEEN()).add(Search.FROM('mailer-daemon@googlemail.com')).add(
            Search.SUBJECT("Delivery Status Notification"))

        message_ids = self.search_email(*criteria, connector=connector)
        emails = self.read_email(message_ids, connector, max_count=max_count,)
        events = []

        for ids, email in zip(message_ids, emails):
            original_message = email.Message_RFC882
            if original_message.Email_ID == None:
                continue

            email_id_extracted = extract_email_id_from_msgid(original_message.Message_ID, self.configService.DOMAIN_NAME)
            if email_id_extracted == None:
                continue

            if email_id_extracted != original_message.Email_ID:
                continue
            bs4 = BeautifulSoup(email.HTML_Body, 'html.parser')
            last_p = bs4.body
            if last_p == None:
                continue
            # Get the last <p> element in the body
            last_p = last_p.find_all('p')[-1]
            text = last_p.get_text(strip=True)

            try:
                smtp_error_code = SMTPErrorCode(text[:10])
            except:
                smtp_error_code = None

            email_status = map_smtp_error_to_status(smtp_error_code)
            error_description = get_error_description(smtp_error_code)

            event = TrackingEmailEventORM.JSON(
                event_id=uuid_v1_mc(),
                description=error_description,
                email_id=original_message.Email_ID,
                # contact_id=None,
                current_event=email_status.value,
                date_event_received=datetime.now(timezone.utc).isoformat(),
                esp_provider=get_email_provider_name(original_message.From)
            )
            events.append(event)
            # self.delete_email(ids,connector)
        return None, (StreamConstant.EMAIL_EVENT_STREAM,events),{}

    # @EmailReadInterface.register_job('Parse Replied Email',(60,180),'INBOX', None,True)
    # @EmailReadInterface.register_job('Parse Forwarded Email',(60,180),'INBOX', None,False)
    @ProfileEventInterface.EventWrapper
    @BaseEmailService.Lifecycle('async')
    @select_inbox
    def forwarded_email(self, max_count: int | None, is_re: bool, connector: imap.IMAP4 | imap.IMAP4_SSL):
        criteria = IMAPCriteriaBuilder()
        criteria.add(Search.UNSEEN()).add(
            Search.SUBJECT('Re:'if is_re else 'Fwd:'))
        message_ids = self.search_email(*criteria, connector=connector)
        emails = self.read_email(message_ids, connector, max_count=max_count,)
        events = []

        verb = 'replied' if is_re else 'forwarded'
        for ids, e in zip(message_ids, emails):
            original_message = e.Message_RFC882

            if original_message == None:  # the original message was partially appended
                From = e.From
                description = f"{From} has {verb} to  the email"
                if is_re:
                    email_id = e.In_Reply_To
                else:
                    email_id = e.Get_Our_Last_Message_References(
                        self.configService.DOMAIN_NAME)
                email_id = extract_email_id_from_msgid(
                    email_id, self.configService.DOMAIN_NAME)
                if email_id == None:
                    continue

            else:
                if original_message.Email_ID == None:  # The full original message was appended
                    continue
                email_id_extracted = extract_email_id_from_msgid(
                    original_message.Message_ID, self.configService.DOMAIN_NAME)
                if email_id_extracted == None:
                    continue
                if email_id_extracted != original_message.Email_ID:
                    continue
                From = original_message.From
                description = f"{From} has {verb} to the email"
                email_id = original_message.Email_ID

            event = TrackingEmailEventORM.JSON(
                event_id=uuid_v1_mc(),
                description=description,
                email_id=email_id,
                # contact_id=None,
                current_event=EmailStatus.REPLIED,
                date_event_received=datetime.now(timezone.utc).isoformat(),
                esp_provider=get_email_provider_name(From)
            )
            events.append(event)
        return None,(StreamConstant.EMAIL_EVENT_STREAM, event),{}

    @property
    def mailboxes(self):
        return self._mailboxes.keys()

    @property
    def capabilities(self):
        return self._capabilities

    @property
    def has_thread_capabilities(self):
        return 'THREAD=REFERENCES' in self._capabilities or 'THREAD=ORDEREDSUBJECT' in self._capabilities

# @_service.Service()Class

