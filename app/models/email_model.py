from typing import Any, List, Literal, Optional, Self, TypeVar, TypedDict
from pydantic import BaseModel, model_validator
from enum import Enum
from tortoise import fields, models, Tortoise, run_async
from tortoise.transactions import in_transaction
from app.classes.celery import SchedulerModel
from app.classes.email import MimeType
from app.classes.mail_provider import SMTPErrorCode
from app.utils.helper import uuid_v1_mc

SCHEMA = 'emails'

class EmailMetaModel(BaseModel):
    Subject: str
    From: str
    To: str | List[str]
    CC: Optional[str] = None
    Bcc: Optional[str] = None
    replyTo: Optional[str] = None
    Priority: Literal['1', '3', '5'] = '1'
    Disposition_Notification_To:str|None = None
    Return_Receipt_To:str|None = None
    Message_ID:str|None = None
    X_Email_ID:str|None =None

    @model_validator(mode="after")
    def meta_validator(self)->Self:
        self.Disposition_Notification_To = None
        self.Return_Receipt_To = None
        self.Message_ID = None
        self.X_Email_ID = None
        return self

class EmailTemplateModel(BaseModel):
    meta: EmailMetaModel
    data: dict[str, Any]
    attachments: Optional[dict[str, Any]] = {}
    mimeType:MimeType = 'both'

class CustomEmailModel(BaseModel):
    meta: EmailMetaModel
    text_content: str|None = None
    html_content: str|None = None
    attachments: Optional[List[tuple[str, str]]] = []
    images: Optional[List[tuple[str, str]]] = []

class EmailSpamDetectionModel(BaseModel):
    recipient:str |List[str] | None
    body_plain:str |None
    body_html:str | None
    subject:str

    @model_validator(mode="after")
    def body_validator(self)->Self:
        if self.body_html == None and self.body_plain == None:
            raise ValueError('Plain body and Html body cannot both be null')
        return self

class EmailStatus(str, Enum):
    RECEIVED='RECEIVED'
    SENT = 'SENT'
    DELIVERED = 'DELIVERED'
    SOFT_BOUNCE = 'SOFT-BOUNCE'
    HARD_BOUNCE = 'HARD-BOUNCE'
    MAILBOX_FULL = 'MAILBOX-FULL'
    OPENED = 'OPENED'
    LINK_CLICKED = 'LINK-CLICKED'
    FAILED = 'FAILED'
    BLOCKED = 'BLOCKED'
    COMPLAINT = 'COMPLAINT'
    DEFERRED = 'DEFERRED'
    DELAYED = 'DELAYED'
    REPLIED = 'REPLIED'


mapping = {
        SMTPErrorCode.MAILBOX_UNAVAILABLE: EmailStatus.HARD_BOUNCE,
        SMTPErrorCode.USER_UNKNOWN: EmailStatus.HARD_BOUNCE,
        SMTPErrorCode.POLICY_RESTRICTIONS: EmailStatus.BLOCKED,
        SMTPErrorCode.TEMP_SERVER_ERROR: EmailStatus.DEFERRED,
        SMTPErrorCode.CONNECTION_TIMEOUT: EmailStatus.DELAYED,
        SMTPErrorCode.AUTH_CREDENTIALS_INVALID: EmailStatus.FAILED,
    }

def map_smtp_error_to_status(error_code: SMTPErrorCode|str) -> EmailStatus:
    """
    Maps an SMTPErrorCode to the most probable EmailStatus.

    Args:
        error_code (SMTPErrorCode): The SMTP error code to map.

    Returns:
        EmailStatus: The corresponding EmailStatus.
    """

    if isinstance(error_code,str):
        try:
            error_code = SMTPErrorCode(error_code)
        except:
            return EmailStatus.FAILED
    
    return mapping.get(error_code, EmailStatus.FAILED)
 

class EmailTrackingORM(models.Model):
    email_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    """
    Email ID generated for database PK
    """

    message_id = fields.CharField(max_length=150, unique=True)
    """
    Message ID generated for the smtp email transactions
    """
    recipient = fields.CharField(max_length=100)
    subject = fields.CharField(max_length=150)
    esp_provider = fields.CharField(max_length=30)
    date_sent = fields.DatetimeField(auto_now=True)
    last_update = fields.DatetimeField(auto_now_add=True)
    expired_tracking_date = fields.DatetimeField(null=True)
    email_current_status = fields.CharEnumField(EmailStatus, null=True)
    spam_label = fields.CharField(max_length=50, null=True)
    spam_detection_confidence = fields.FloatField(null=True)

    class Meta:
        schema = SCHEMA
        table = "emailtracking"

    @property
    def to_json(self):
        return {
            "email_id": str(self.email_id),
            "message_id": self.message_id,
            "recipient": self.recipient,
            'esp_provider':self.esp_provider,
            "date_sent": self.date_sent.isoformat(),
            "last_update": self.last_update.isoformat(),
            "expired_tracking_date": self.expired_tracking_date.isoformat() if self.expired_tracking_date else None,
            "email_current_status": self.email_current_status.value if self.email_current_status else None,
            "spam_label": self.spam_label,
            "spam_detection_confidence": self.spam_detection_confidence
        }

class TrackingEmailEventORM(models.Model):
    event_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    email = fields.ForeignKeyField("models.EmailTrackingORM", related_name="events", on_delete=fields.CASCADE)
    contact = fields.ForeignKeyField("models.ContactORM",'contact',on_delete=fields.NO_ACTION)
    description = fields.CharField(max_length=100,null=True)
    current_event = fields.CharEnumField(EmailStatus)
    date_event_received = fields.DatetimeField(auto_now_add=True)


    class TrackingEventJSON(TypedDict):
        event_id:str
        description:str=None
        email_id:str|None
        contact_id:str|None
        current_event:str|None
        date_event_received:str
        
    class Meta:
        schema = SCHEMA
        table = "trackingevent"

    @property
    def to_json(self):
        return {
            "event_id": str(self.event_id),
            "description":self.description,
            "email_id": str(self.email.email_id),
            "contact_id":str(self.contact.contact_id),
            "current_event": self.current_event.value,
            "date_event_received": self.date_event_received.isoformat()
        }

class TrackedLinksORM(models.Model):
    link_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    email = fields.ForeignKeyField("models.EmailTrackingORM", related_name="tracked_links", on_delete=fields.CASCADE)
    link_url = fields.CharField(max_length=150, unique=True)
    click_count = fields.IntField(default=0)

    class Meta:
        schema = SCHEMA
        table = "trackedlinks"

    @property
    def to_json(self):
        return {
            "link_id": str(self.link_id),
            "email_id": str(self.email_id),
            "link_url": self.link_url,
            "click_count": self.click_count
        }

class EmailAnalyticsORM(models.Model):
    analytics_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    week_start_date = fields.DateField(unique=True)
    emails_sent = fields.IntField(default=0)
    emails_delivered = fields.IntField(default=0)
    emails_opened = fields.IntField(default=0)
    emails_bounced = fields.IntField(default=0)
    emails_replied = fields.IntField(default=0)

    class Meta:
        schema = SCHEMA
        table = "emailanalytics"

    @property
    def to_json(self):
        return {
            "analytics_id": str(self.analytics_id),
            "week_start_date": self.week_start_date.isoformat(),
            "emails_sent": self.emails_sent,
            "emails_delivered": self.emails_delivered,
            "emails_opened": self.emails_opened,
            "emails_bounced": self.emails_bounced,
            "emails_replied": self.emails_replied,
        }


async def upsert_email_analytics(sent: int, delivered: int, opened: int, bounced: int, replied: int):
    """
    Upserts email analytics data into the database.

    Args:
        sent (int): Number of emails sent.
        delivered (int): Number of emails delivered.
        opened (int): Number of emails opened.
        bounced (int): Number of emails bounced.
        replied (int): Number of emails replied.

    Returns:
        None
    """
    print(sent)
    query = "SELECT emails.upsert_email_analytics($1, $2, $3, $4, $5);"
    client = Tortoise.get_connection('default')
    await client.execute_query(query, [sent, delivered, opened, bounced, replied])




async def calculate_email_analytics_grouped(group_by_factor: int):
    """
    Fetches grouped email analytics based on the specified grouping factor.

    Args:
        group_by_factor (int): The grouping factor (e.g., 1 for weeks, 4 for months, etc.).

    Returns:
        List[dict]: List of grouped analytics as dictionaries.
    """
    query = "SELECT * FROM emails.calculate_email_analytics_grouped($1);"
    client = Tortoise.get_connection('default')
    rows = await client.execute_query(query, [group_by_factor])
    return [
        {
            "group_number": row[0],
            "emails_sent": row[1],
            "emails_delivered": row[2],
            "emails_opened": row[3],
            "emails_bounced": row[4],
            "emails_replied": row[5],
        }
        for row in rows[1]
    ]
