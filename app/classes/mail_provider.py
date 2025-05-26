from dataclasses import dataclass, field
import smtplib as smtp
import imaplib as imap
from enum import Enum
from typing import Callable, Iterable, Literal, Self, overload
from .mail_oauth_access import GoogleFlowType,MailOAuthFactory
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from base64 import urlsafe_b64encode, urlsafe_b64decode


SMTP_NORMAL_PORT = smtp.SMTP_PORT
SMTP_SSL_PORT = smtp.SMTP_SSL_PORT
SMTP_TLS_PORT = 587


IMAP_NORMAL_PORT = 143
IMAP_SSL_TLS_PORT = 993

ConnMode = Literal['tls', 'ssl', 'normal']

provider_map = {
        # Google domains
        "gmail": "Google",
        "googlemail": "Google",
        "google": "Google",

        # Microsoft domains
        "hotmail": "Microsoft",
        "outlook": "Microsoft",
        "live": "Microsoft",
        "msn": "Microsoft",

        # Yahoo domains
        "yahoo": "Yahoo",
        "ymail": "Yahoo",
        "rocketmail": "Yahoo",

        # Apple
        "icloud": "Apple",
        "me": "Apple",
        "mac": "Apple",

        # ProtonMail
        "protonmail": "ProtonMail",

        # Zoho
        "zoho": "Zoho",

        # AOL
        "aol": "AOL",

        # Example fallback
        "example": "Example Provider"
    }

class SMTPErrorCode(Enum):
    MAILBOX_UNAVAILABLE = "550 5.5.0"
    USER_UNKNOWN = "550 5.1.1"
    POLICY_RESTRICTIONS = "554 5.7.1"
    TEMP_SERVER_ERROR = "451 4.3.0"
    CONNECTION_TIMEOUT = "421 4.4.2"
    AUTH_CREDENTIALS_INVALID = "535 5.7.8"

error_descriptions = {
    SMTPErrorCode.MAILBOX_UNAVAILABLE: "Requested action not taken: mailbox unavailable.",
    SMTPErrorCode.USER_UNKNOWN: "Recipient address rejected: User unknown.",
    SMTPErrorCode.POLICY_RESTRICTIONS: "Message rejected due to policy restrictions.",
    SMTPErrorCode.TEMP_SERVER_ERROR: "Temporary server error. Please try again later.",
    SMTPErrorCode.CONNECTION_TIMEOUT: "Connection timed out. Try again later.",
    SMTPErrorCode.AUTH_CREDENTIALS_INVALID: "Authentication credentials invalid or not accepted.",
}

def get_error_description(error_code:SMTPErrorCode):
    return error_descriptions.get(error_code,'Unknown error to our server')

class EmailConnInterface():
    def setHostPort(connMode: str): pass

    def setConnFlag(mode: str): pass

    def setHostAddr(host: str): pass

class SMTPConfig(EmailConnInterface, Enum):

    GMAIL_RELAY = "smtp-relay.gmail.com"
    GMAIL_RESTRICTED = 'aspmx.l.google.com'
    GMAIL = "smtp.gmail.com"
    OUTLOOK = "smtp.office365.com"
    YAHOO = "smtp.mail.yahoo.com"
    AOL = 'smtp.aol.com'
    ICLOUD = 'smtp.mail.me.com'

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
        host = host.upper().strip()
        if host in SMTPConfig._member_names_:
            return SMTPConfig._member_map_[host].value
        return host

class IMAPConfig (EmailConnInterface, Enum):
    """The IMAPHost class is an enumeration of the IMAP host names for the two email providers that I use
    """
    GMAIL = "imap.gmail.com"
    YAHOO = "imap.mail.yahoo.com"
    OUTLOOK = "outlook.office365.com"  # BUG potentiel : might not work

    def setHostAddr(host: str) -> str | None:
        host = host.upper().strip()
        if host in IMAPConfig._member_names_:
            return IMAPConfig._member_map_[host].value
        return None

    def setConnFlag(mode: str): return mode.lower() == "tls"

    def setHostPort(mode: str): return IMAP_SSL_TLS_PORT if mode.lower(
    ).strip() == "ssl" else IMAP_NORMAL_PORT

class IMAPSearchFilter(Enum):
    UNSEEN = lambda:"UNSEEN"
    FROM = lambda f:("FROM",f)
    SUBJECT = lambda s:("SUBJECT",s)
    SINCE = lambda d:("SINCE",d)
    ALL= lambda:'ALL'

@dataclass
class IMAPCriteriaBuilder:
    criteria = field(default_factory=list)

    @overload
    def add(self,*criteria:str)->Self:
        ...
    
    @overload
    def add(self,criteria:Iterable[str])->Self:
        ...


    def add(self,criteria:Iterable[str])->Self:
        self.criteria.extend(criteria)
        return self

    def __iter__(self):
        return self.criteria.__iter__()
    

class MailAPI:
    ...


class GMailAPI(MailAPI):
    def __init__(self, flowtype: GoogleFlowType, credentials):
        """
        Initializes the GMailAPI with a specific Google OAuth2 flow type and credentials.

        Args:
            flowtype (GoogleFlowType): The type of Google OAuth flow used.
            credentials (google.oauth2.credentials.Credentials): OAuth2 credentials.
        """
        super().__init__()
        self.flowtype = flowtype
        self.credentials = credentials
        self.service = build('gmail', 'v1', credentials=self.credentials)

    def send_email(self,message:str):
        try:

            # Encode the message as base64
            #encoded_message = urlsafe_b64encode(message.as_bytes()).decode()
            encoded_message = ...
            # Send the message
            create_message = {'raw': encoded_message}
            sent_message = self.service.users().messages().send(userId='me', body=create_message).execute()
            return sent_message
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None

    def list_messages(self, query='', max_results=10):
        try:
            response = self.service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
            messages = response.get('messages', [])
            return messages
        except HttpError as error:
            print(f"An error occurred: {error}")
            return []

    def get_message(self, message_id):
        try:
            message = self.service.users().messages().get(userId='me', id=message_id, format='full').execute()
            return message
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None

    def list_labels(self):
        try:
            response = self.service.users().labels().list(userId='me').execute()
            labels = response.get('labels', [])
            return labels
        except HttpError as error:
            print(f"An error occurred: {error}")
            return []

class MicrosoftGraphMailAPI(MailAPI):
    ...

def get_email_provider_name(email):
    
    try:
        domain = email.split('@')[1]
        subdomain = domain.split('.')[0].lower()

        return provider_map.get(subdomain, "Unknown Provider")
    except (IndexError, AttributeError):
        return "Invalid Email"
