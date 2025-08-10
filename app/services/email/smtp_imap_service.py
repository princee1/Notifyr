
import asyncio
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
import functools
from random import randint
import re
import smtplib as smtp
import imaplib as imap
import poplib as pop
import socket
from typing import Callable, Iterable, Literal, Self, Type, TypedDict

from bs4 import BeautifulSoup

from app.interface.timers import IntervalInterface
from app.services.aws_service import AmazonSESService
from app.services.database_service import RedisService
from app.services.reactive_service import ReactiveService
from app.utils.helper import get_value_in_list, uuid_v1_mc
from app.utils.prettyprint import SkipInputException
from app.classes.mail_oauth_access import OAuth, MailOAuthFactory, OAuthFlow
from app.classes.mail_provider import IMAPCriteriaBuilder, SMTPConfig, IMAPConfig, IMAPSearchFilter as Search, SMTPErrorCode, get_email_provider_name, get_error_description
from app.utils.tools import Time,Mock

from app.utils.constant import EmailHostConstant
from app.classes.email import EmailBuilder, EmailMetadata, EmailReader, NotSameDomainEmailError, extract_email_id_from_msgid

from ..logger_service import LoggerService
from app.definition import _service
from ..config_service import CeleryMode, ConfigService
import ssl

from app.models.email_model import EmailStatus, EmailTrackingORM, TrackingEmailEventORM, map_smtp_error_to_status
from app.utils.validation import email_validator

from app.utils.constant import StreamConstant
from email import message_from_bytes
from app.interface.redis_event import RedisEventInterface
from app.interface.email import EmailSendInterface



@_service.AbstractServiceClass
class BaseEmailService(_service.BaseService, RedisEventInterface,EmailSendInterface):

    def __init__(self, configService: ConfigService, loggerService: LoggerService, redisService: RedisService):
        super().__init__()
        EmailSendInterface.__init__(self)
        self.configService: ConfigService = configService
        self.loggerService: LoggerService = loggerService
        RedisEventInterface.__init__(self, redisService)
        self.hostPort: int
        self.mailOAuth: OAuth = ...
        self.state = None
        self.connMethod = ...
        self.last_connectionTime: float = ...
        self.emailHost: EmailHostConstant = ...
        self.type_: Literal['IMAP', 'SMTP'] = None

    @staticmethod
    def task_lifecycle(pref: Literal['async', 'sync'] = None, async_callback: Callable = None, sync_callback: Callable = None):

        def callback(func: Callable):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                use_ses = kwargs.get('use_ses',False)

                self: BaseEmailService = args[0]
                if not isinstance(self, BaseEmailService):
                    self = self.__class__.service

                if not use_ses:
                    connector = self.connect()
                    if connector == None:
                        return

                    if not self.authenticate(connector):
                        return
                
                    kwargs['connector'] = connector

                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                if callable(async_callback):
                    await async_callback(self, *result[1], **result[2])
                    result = result[0]
                else:
                    if isinstance(result, (list, tuple)):
                        result = result[0]
                if not use_ses:
                    self.logout(connector)
                return result

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                self: BaseEmailService = args[0]
                if not isinstance(self, BaseEmailService):
                    self = self.__class__.service

                connector = self.connect()
                if connector == None:
                    return

                if not self.authenticate(connector):
                    return
                kwargs['connector'] = connector
                result = func(*args, **kwargs)

                if callable(sync_callback):
                    sync_callback(self, *result[1], **result[2])
                    result = result[0]
                else:
                    if isinstance(result, tuple):
                        result = result[0]

                self.logout(connector)
                return result

            if ConfigService._celery_env == CeleryMode.worker:
                return sync_wrapper

            if pref == 'async':
                return async_wrapper

            if pref == 'sync':
                return sync_wrapper

            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

        return callback

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
        config: type[SMTPConfig |
                     IMAPConfig] = SMTPConfig if self.type_ == 'SMTP' else IMAPConfig
        server_type_ssl: type = smtp.SMTP_SSL if self.type_ == 'SMTP' else imap.IMAP4_SSL
        server_type: type = smtp.SMTP if self.type_ == 'SMTP' else imap.IMAP4
        try:
            self.hostAddr = config.setHostAddr(
                self.configService.SMTP_EMAIL_HOST)
            if self.connMethod == 'ssl':
                connector = server_type_ssl(self.hostAddr, self.hostPort)
            else:
                connector = server_type(self.hostAddr, self.hostPort)

            if self.type_ == 'SMTP':
                connector.set_debuglevel(
                    self.configService.SMTP_EMAIL_LOG_LEVEL)
            return connector
        except (socket.gaierror, ConnectionRefusedError, TimeoutError) as e:
            self.service_status = _service.ServiceStatus.NOT_AVAILABLE

        except ssl.SSLError as e:
            self.service_status = _service.ServiceStatus.NOT_AVAILABLE

        except NameError as e:
            # BUG need to change the error name and a builder error
            self.service_status = _service.ServiceStatus.NOT_AVAILABLE

        return None

    def logout(self): ...

    def resetConnection(self): ...

    def help(self):
        ...


@_service.Service
class SMTPEmailService(BaseEmailService):
    # BUG cant resolve an abstract class
    def __init__(self, configService: ConfigService, loggerService: LoggerService, redisService: RedisService,awsSESService:AmazonSESService):
        super().__init__(configService, loggerService, redisService)
        self.type_ = 'SMTP'
        self.fromEmails: set[str] = set()
        self.connMethod = self.configService.SMTP_EMAIL_CONN_METHOD.lower()
        self.tlsConn: bool = SMTPConfig.setConnFlag(self.connMethod)
        self.hostPort = SMTPConfig.setHostPort(
            self.configService.SMTP_EMAIL_CONN_METHOD) if self.configService.SMTP_EMAIL_PORT == None else self.configService.SMTP_EMAIL_PORT

        self.emailHost = EmailHostConstant._member_map_[
            self.configService.SMTP_EMAIL_HOST]
    
        self.awsSESService = awsSESService

    def logout(self, connector: smtp.SMTP):
        try:
            connector.quit()
            connector.close()
        except:
            ...

    def verify_dependency(self):
        if self.configService.SMTP_EMAIL_HOST not in EmailHostConstant._member_names_:
            raise _service.BuildFailureError

    def authenticate(self, connector: smtp.SMTP):

        try:
            if self.tlsConn:
                context = ssl.create_default_context()
                connector.ehlo()
                connector.starttls(context=context)
                connector.ehlo()

            if self.emailHost in [EmailHostConstant.ICLOUD, EmailHostConstant.GMAIL, EmailHostConstant.GMAIL_RELAY, EmailHostConstant.GMAIL_RESTRICTED] and self.configService.SMTP_PASS != None:

                auth_status = connector.login(
                    self.configService.SMTP_EMAIL, self.configService.SMTP_PASS)
            else:
                access_token = self.mailOAuth.encode_token(
                    self.configService.SMTP_EMAIL)
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

    @Mock()
    @BaseEmailService.task_lifecycle('async', *RedisEventInterface.redis_event_callback)
    def sendTemplateEmail(self, data, meta, images,contact_id=None, connector: smtp.SMTP = None):
        meta = EmailMetadata(**meta)
        email = EmailBuilder(data, meta, images)
        return self._send_message(email, contact_ids=contact_id, connector=connector)

    @Mock()
    @BaseEmailService.task_lifecycle('async', *RedisEventInterface.redis_event_callback)
    def sendCustomEmail(self, content, meta, images, attachment,contact_id=None, connector: smtp.SMTP = None):
        meta = EmailMetadata(**meta)
        email = EmailBuilder(content, meta, images, attachment)
        return self._send_message(email, contact_ids=contact_id, connector=connector)

    @BaseEmailService.task_lifecycle('async', *RedisEventInterface.redis_event_callback)
    def reply_to_an_email(self, content, meta, images, attachment, reply_to, references, connector: smtp.SMTP = None, contact_ids:list[str]=None):
        meta = EmailMetadata(**meta)
        email = EmailBuilder(content, meta, images, attachment)
        # TODO add references and reply_to

        # if self.configService.celery_env == CeleryMode.none:
        #     return await self._send_message(email, message_tracking_id, contact_id=contact_id)
        return self._send_message(email,contact_ids=contact_ids, connector=connector)

    def _send_message(self, email: EmailBuilder, connector: smtp.SMTP, contact_ids:list[ str] = [],use_ses=False):
        replies = []
        events = []
        for i,(emailID, message) in enumerate(email.create_for_recipient()):

            try:
                if not use_ses:
                    event_id = str(uuid_v1_mc())
                    now = datetime.now(timezone.utc).isoformat()
                    reply_ = None
                    reply_ = connector.sendmail(email.emailMetadata.From, email.To[i], message, rcpt_options=[
                                                'NOTIFY=SUCCESS,FAILURE,DELAY'])
                    email_status = EmailStatus.SENT.value
                    description = "Email successfully sent."
                else:
                    ...

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
                self.service_status = _service.ServiceStatus.NOT_AVAILABLE
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
                        esp_provider=get_email_provider_name(
                            email.emailMetadata.To[i])
                    )
                    events.append(event)

                replies.append( {"emailID": emailID,"status": reply_})

        return replies, (StreamConstant.EMAIL_EVENT_STREAM, [event]), {}

    @BaseEmailService.task_lifecycle()
    def verify_same_domain_email(self, email: str, connector: smtp.SMTP):
        domain = email.split['@'][1]
        our_domain = self.configService.SMTP_EMAIL.split['@'][1]
        if our_domain != domain:
            raise NotSameDomainEmailError

        return (connector.verify(email),)


J: Type = None
j: dict = None


@_service.Service
class IMAPEmailService(BaseEmailService):
    service: Self  # Class Singleton

    @dataclass
    class Jobs:
        job_name: str
        func: str
        args: Iterable
        kwargs: dict
        stop: bool = True
        task: asyncio.Task = None
        delay: int = field(default_factory=lambda: randint(3600/2, 3600))

        async def __call__(self,):
            service: IMAPEmailService = IMAPEmailService.service
            callback = getattr(service, self.func, None)
            is_async = asyncio.iscoroutinefunction(callback)
            while self.stop:
                self.is_running = False
                await asyncio.sleep(self.delay)
                self.is_running = True

                if is_async:
                    print('Ok')
                    await callback(*self.args, **self.kwargs)
                else:
                    print('k')

                    callback(*self.args, **self.kwargs)
            return

        def cancel_job(self):
            self.stop = False
            self.delay = 0

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

        @BaseEmailService.task_lifecycle()
        def rename(self, new_name: str, connector: imap.IMAP4 | imap.IMAP4_SSL):
            """Rename the mailbox."""
            status, response = connector.rename(self.name, new_name)
            if status != 'OK':
                raise imap.IMAP4.error(
                    f"Failed to rename mailbox {self.name} to {new_name}")
            self.name = new_name
            return (response,)

        @BaseEmailService.task_lifecycle()
        def delete(self, connector: imap.IMAP4 | imap.IMAP4_SSL):
            """Delete the mailbox."""
            status, response = connector.delete(self.name)
            if status != 'OK':
                raise imap.IMAP4.error(f"Failed to delete mailbox {self.name}")
            return (response,)

        @BaseEmailService.task_lifecycle()
        def create_subfolder(self, subfolder_name: str, connector: imap.IMAP4 | imap.IMAP4_SSL):
            """Create a subfolder under the current mailbox."""
            full_name = f"{self.name}/{subfolder_name}"
            status, response = connector.create(full_name)
            if status != 'OK':
                raise imap.IMAP4.error(
                    f"Failed to create subfolder {subfolder_name} under {self.name}")
            return ((full_name, response),)

        @BaseEmailService.task_lifecycle()
        def status(self, connector: imap.IMAP4 | imap.IMAP4_SSL):
            ...

    jobs: dict[str, Jobs] = {}

    global J
    J = Jobs
    global j
    j = jobs

    @staticmethod
    def select_inbox(func: Callable):

        def callback(self: Self, inbox: str, kwargs):
            if inbox not in self.mailboxes:
                raise KeyError('Mail box not found')

            if self._mailboxes[inbox].no_select:
                raise imap.IMAP4.error(f'This inbox cannot be selected')

            self._current_mailbox = inbox
            connector: imap.IMAP4 | imap.IMAP4_SSL = kwargs['connector']
            connector.select(inbox)

        @functools.wraps(func)
        def wrapper(self: Self, inbox: str, *args, **kwargs):
            callback(self, inbox, kwargs)
            return func(self, *args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(self: Self, inbox: str, *args, **kwargs):
            callback(self, inbox, kwargs)
            return await func(self, *args, **kwargs)

        return wrapper if not asyncio.iscoroutinefunction(func) else async_wrapper

    @staticmethod
    def register_job(job_name: str, delay: tuple[int, int], *args, **kwargs):

        def wrapper(func: Callable):
            func_name = func.__name__
            job_name_prime = job_name if job_name else func_name
            params = {
                'job_name': job_name_prime,
                'func': func_name,
                'args': args,
                'kwargs': kwargs
            }
            if delay == None or not isinstance(delay, tuple):
                ...
            else:
                params['delay'] = randint(*delay)

            jobs_ = J(**params)
            if job_name_prime in j:
                ...  # Warning
            j[job_name_prime] = jobs_
            return func
        return wrapper

    def __init__(self, configService: ConfigService, loggerService: LoggerService, reactiveService: ReactiveService, redisService: RedisService) -> None:
        super().__init__(configService, loggerService, redisService)
        IntervalInterface.__init__(self, True, 10)
        self.reactiveService = reactiveService
        self.redisService = redisService

        self._mailboxes: dict[str, IMAPEmailService.IMAPMailboxes] = {}
        self._current_mailbox: str = None

        self._init_config()
        IMAPEmailService.service = self
        self._capabilities: list = None

    def _init_config(self):
        self.type_ = 'IMAP'
        self.connMethod = self.configService.IMAP_EMAIL_CONN_METHOD.lower()
        self.tlsConn: bool = IMAPConfig.setConnFlag(self.connMethod)

        self.emailHost = EmailHostConstant._member_map_[
            self.configService.IMAP_EMAIL_HOST]
        self.hostPort = IMAPConfig.setHostPort(
            self.configService.IMAP_EMAIL_CONN_METHOD) if self.configService.IMAP_EMAIL_PORT == None else self.configService.IMAP_EMAIL_PORT

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

    def authenticate(self, connector: imap.IMAP4 | imap.IMAP4_SSL):

        try:
            if self.tlsConn:
                context = ssl.create_default_context()
                connector.starttls(context=context)
            if self.emailHost in [EmailHostConstant.ICLOUD, EmailHostConstant.GMAIL, EmailHostConstant.GMAIL_RELAY, EmailHostConstant.GMAIL_RESTRICTED] and self.configService.IMAP_PASS is not None:
                status, data = connector.login(
                    self.configService.IMAP_EMAIL, self.configService.IMAP_PASS)
                if status != 'OK':
                    raise Exception

                self._update_mailboxes(connector)
                self._get_capabilities(connector)

                return True
            else:
                self.service_status = _service.ServiceStatus.NOT_AVAILABLE
                return False
                access_token = self.mailOAuth.encode_token(
                    self.configService.IMAP_EMAIL)
                auth_code, auth_message = connector.authenticate(
                    'AUTH XOAUTH2', access_token)
                if auth_code != 'OK':
                    raise imap.IMAP4.error(
                        f"Authentication failed: {auth_message}")

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

    def read_email(self, message_ids, connector: imap.IMAP4 | imap.IMAP4_SSL, max_count: int = None):
        for num in message_ids[:max_count]:
            status, data = connector.fetch(num, "(RFC822)")
            if status != 'OK':
                continue
            raw_email = data[0][1]
            msg = message_from_bytes(raw_email)
            yield EmailReader(msg)

    def logout(self, connector: imap.IMAP4 | imap.IMAP4_SSL):
        try:
            connector.close()
            connector.logout()
        except:
            ...

    def build(self):
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

    def start_jobs(self):
        for jobs in self.jobs.values():
            asyncio.create_task(jobs())

    def cancel_jobs(self):
        for jobs in self.jobs.values():
            jobs.cancel_job()

    # @register_job('Parse DNS Email',(60,180),'INBOX', None)
    @BaseEmailService.task_lifecycle()
    @select_inbox
    async def parse_dns_email(self, max_count, connector: imap.IMAP4 | imap.IMAP4_SSL):
        criteria = IMAPCriteriaBuilder()
        criteria.add(Search.UNSEEN()).add(Search.FROM('mailer-daemon@googlemail.com')).add(
            Search.SUBJECT("Delivery Status Notification"))

        message_ids = self.search_email(*criteria, connector=connector)
        emails = self.read_email(message_ids, connector, max_count=max_count,)

        for ids, email in zip(message_ids, emails):
            original_message = email.Message_RFC882
            if original_message.Email_ID == None:
                continue

            email_id_extracted = extract_email_id_from_msgid(
                original_message.Message_ID, self.configService.HOSTNAME)
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

            await self.redisService.stream_data(StreamConstant.EMAIL_EVENT_STREAM, event)
            # self.delete_email(ids,connector)
        return None

    # @register_job('Parse Replied Email',(60,180),'INBOX', None,True)
    # @register_job('Parse Forwarded Email',(60,180),'INBOX', None,False)
    @BaseEmailService.task_lifecycle()
    @select_inbox
    async def forwarded_email(self, max_count: int | None, is_re: bool, connector: imap.IMAP4 | imap.IMAP4_SSL):
        criteria = IMAPCriteriaBuilder()
        criteria.add(Search.UNSEEN()).add(
            Search.SUBJECT('Re:'if is_re else 'Fwd:'))
        message_ids = self.search_email(*criteria, connector=connector)
        emails = self.read_email(message_ids, connector, max_count=max_count,)

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
                        self.configService.HOSTNAME)
                email_id = extract_email_id_from_msgid(
                    email_id, self.configService.HOSTNAME)
                if email_id == None:
                    continue

            else:
                if original_message.Email_ID == None:  # The full original message was appended
                    continue
                email_id_extracted = extract_email_id_from_msgid(
                    original_message.Message_ID, self.configService.HOSTNAME)
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

            await self.redisService.stream_data(StreamConstant.EMAIL_EVENT_STREAM, event)

        return None

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

