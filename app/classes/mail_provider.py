import smtplib as smtp
import imaplib as imap
from enum import Enum
from typing import Literal
from .mail_oauth_access import GoogleFlowType,MailOAuthFactory

SMTP_NORMAL_PORT = smtp.SMTP_PORT
SMTP_SSL_PORT = smtp.SMTP_SSL_PORT
SMTP_TLS_PORT = 587


IMAP_NORMAL_PORT = 143
IMAP_SSL_TLS_PORT = 993

ConnMode = Literal['tls', 'ssl', 'normal']



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
        if host in SMTPConfig._member_names_:
            return SMTPConfig._member_map_[host].value
        return None

    def setConnFlag(mode: str): return mode.lower() == "ssl"

    def setHostPort(mode: str): return IMAP_SSL_TLS_PORT if mode.lower(
    ).strip() == "ssl" else IMAP_NORMAL_PORT


class MailAPI:
    ...


class GMailAPI(MailAPI):
    def __init__(self,flowtype:GoogleFlowType):
        super().__init__()
        self.flowtype = flowtype

class MicrosoftGraphMailAPI(MailAPI):
    ...