from datetime import datetime
from typing import Any, List, Literal, Optional, Self, TypeVar, TypedDict
from pydantic import BaseModel, PrivateAttr, field_validator, model_validator
from enum import Enum
from tortoise import fields, models, Tortoise, run_async
from tortoise.transactions import in_transaction
from app.classes.celery import SchedulerModel
from app.classes.email import MimeType
from app.classes.mail_provider import SMTPErrorCode
from app.utils.helper import uuid_v1_mc
from app.utils.validation import email_validator

SCHEMA = 'emails'


class EmailMetaModel(BaseModel):
    Subject: str
    From: str
    To: str | List[str]
    CC: Optional[str] = None
    Bcc: Optional[str] = None
    replyTo: Optional[str] = None
    Priority: Literal['1', '3', '5'] = '1'
    Disposition_Notification_To: str | None = None
    Return_Receipt_To: str | None = None
    Message_ID: str | None = None
    X_Email_ID: str | None = None
    as_individual:bool = False
    as_contact:bool = False # special_key
    _contact:str|None =PrivateAttr(default=None)
    

    @model_validator(mode="after")
    def meta_validator(self) -> Self:
        self.Disposition_Notification_To = None
        self.Return_Receipt_To = None
        self.Message_ID = None
        self.X_Email_ID = None
        return self
    
    @model_validator(mode="after")
    def To_validator(self:Self)->Self:
        if isinstance(self.To,str):
            if not self.as_contact and not email_validator(self.To):
                raise ValueError('Email format not valid. Hint: It is a contact set as_contact=True')
            self.To = [self.To]
            return self
            
        for email in self.To:
            if not self.as_contact and not email_validator(email):
                raise ValueError('Email format not valid. Hint: It is a contact set as_contact=True')
            
        if self.as_individual:   
            return self
        
        self.To = [','.join(self.To)]
        return self
            
    @model_validator(mode="after")
    def CC_validator(self)->Self:
        if self.CC == None:
            return self
        if isinstance(self.CC,str):
            if not email_validator(self.CC):
                raise ValueError('Email format not valid')
            self.CC = [self.CC]
            return self
        

        for email in self.CC:
            if not email_validator(email):
                raise ValueError('Email format not valid')
            
        self.CC = ','.join(self.CC)
        return self



class EmailTemplateModel(BaseModel):
    meta: EmailMetaModel
    data: dict[str, Any]
    attachments: Optional[dict[str, Any]] = {}
    mimeType: MimeType = 'both'


class CustomEmailModel(BaseModel):
    meta: EmailMetaModel
    text_content: str | None = None
    html_content: str | None = None
    attachments: Optional[List[tuple[str, str]]] = []
    images: Optional[List[tuple[str, str]]] = []


class EmailSpamDetectionModel(BaseModel):
    recipient: str | List[str] | None
    body_plain: str | None
    body_html: str | None
    subject: str

    @model_validator(mode="after")
    def body_validator(self) -> Self:
        if self.body_html == None and self.body_plain == None:
            raise ValueError('Plain body and Html body cannot both be null')
        return self


class EmailStatus(str, Enum):
    RECEIVED = 'RECEIVED'
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
    REJECTED = 'REJECTED'


mapping = {
    SMTPErrorCode.MAILBOX_UNAVAILABLE: EmailStatus.HARD_BOUNCE,
    SMTPErrorCode.USER_UNKNOWN: EmailStatus.HARD_BOUNCE,
    SMTPErrorCode.POLICY_RESTRICTIONS: EmailStatus.BLOCKED,
    SMTPErrorCode.TEMP_SERVER_ERROR: EmailStatus.DEFERRED,
    SMTPErrorCode.CONNECTION_TIMEOUT: EmailStatus.DELAYED,
    SMTPErrorCode.AUTH_CREDENTIALS_INVALID: EmailStatus.FAILED,
}


def map_smtp_error_to_status(error_code: SMTPErrorCode | str) -> EmailStatus:
    """
    Maps an SMTPErrorCode to the most probable EmailStatus.

    Args:
        error_code (SMTPErrorCode): The SMTP error code to map.

    Returns:
        EmailStatus: The corresponding EmailStatus.
    """

    if isinstance(error_code, str):
        try:
            error_code = SMTPErrorCode(error_code)
        except:
            return EmailStatus.FAILED

    return mapping.get(error_code, EmailStatus.FAILED)

class EmailTemplateSchedulerModel(SchedulerModel):
    content: EmailTemplateModel | list[EmailTemplateModel]

class CustomEmailSchedulerModel(SchedulerModel):
    content: CustomEmailModel | list[CustomEmailModel]



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
    contact = fields.ForeignKeyField(
        "models.ContactORM", 'contact', null=True, on_delete=fields.NO_ACTION)
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
            "contact_id": str(self.contact.contact_id) if self.contact != None else None,
            'esp_provider': self.esp_provider,
            "date_sent": self.date_sent.isoformat(),
            "last_update": self.last_update.isoformat(),
            "expired_tracking_date": self.expired_tracking_date.isoformat() if self.expired_tracking_date else None,
            "email_current_status": self.email_current_status.value if self.email_current_status else None,
            "spam_label": self.spam_label,
            "spam_detection_confidence": self.spam_detection_confidence
        }


class TrackingEmailEventORM(models.Model):
    event_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    email = fields.ForeignKeyField(
        "models.EmailTrackingORM", related_name="events", on_delete=fields.CASCADE)
    description = fields.CharField(max_length=100, null=True)
    current_event = fields.CharEnumField(EmailStatus)
    date_event_received = fields.DatetimeField(auto_now_add=True)

    class JSON(TypedDict):
        event_id: str
        description: str = None
        email_id: str | None
        esp_provider: str | None
        current_event: str | None
        date_event_received: str
        correction: bool = False

    class Meta:
        schema = SCHEMA
        table = "trackingevent"

    @property
    def to_json(self):
        return {
            "event_id": str(self.event_id),
            "description": self.description,
            "email_id": str(self.email.email_id),
            "current_event": self.current_event.value,
            "date_event_received": self.date_event_received.isoformat()
        }


class TrackedLinksORM(models.Model):
    link_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    email = fields.ForeignKeyField(
        "models.EmailTrackingORM", related_name="tracked_links", on_delete=fields.CASCADE)
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
    day_start_date = fields.DateField(default=datetime.utcnow().date)
    esp_provider = fields.CharField(max_length=25)
    emails_received = fields.IntField(default=0)
    emails_sent = fields.IntField(default=0)
    emails_rejected= fields.IntField(default=0)
    emails_delivered = fields.IntField(default=0)
    emails_opened = fields.IntField(default=0)
    emails_bounced = fields.IntField(default=0)
    emails_complaint = fields.IntField(
        default=0)  # Added emails_complaint field
    emails_replied = fields.IntField(default=0)
    emails_failed = fields.IntField(default=0)  # Added emails_failed field

    class Meta:
        schema = SCHEMA
        table = "emailanalytics"
        unique_together = ("day_date", "esp_provider")

    @property
    def to_json(self):
        return {
            "analytics_id": str(self.analytics_id),
            "day_start_date": self.day_start_date.isoformat(),
            "esp_provider": self.esp_provider,
            "emails_received": self.emails_received,
            "emails_reject":self.emails_rejected,
            "emails_sent": self.emails_sent,
            "emails_delivered": self.emails_delivered,
            "emails_opened": self.emails_opened,
            "emails_bounced": self.emails_bounced,
            "emails_complaint": self.emails_complaint,  # Added emails_complaint
            "emails_replied": self.emails_replied,
            "emails_failed": self.emails_failed,  # Added emails_failed
        }


async def bulk_upsert_email_analytics(data: dict[str, dict]):
    """
    Bulk upsert email analytics data.

    Args:
        data (List[dict]): A list of dictionaries containing analytics data.
    """
    query = """
    SELECT emails.bulk_upsert_email_analytics($1);
    """
    emails_values = [
        (
            esp_provider,
            analytics['received'],
            analytics['sent'],
            analytics['rejected'],
            analytics['delivered'],
            analytics['opened'],
            analytics['bounced'],
            analytics['complaint'],
            analytics['replied'],
            analytics['failed']
        )
        for esp_provider, analytics in data.items()
    ]
    client = Tortoise.get_connection('default')
    await client.execute_query(query, [emails_values])
    

async def calculate_email_analytics_grouped(group_by_factor: int):
    """
    Calculate email analytics grouped by a specified factor.

    Args:
        group_by_factor (int): The grouping factor in days.

    Returns:
        List[dict]: A list of dictionaries containing grouped analytics data.
    """
    query = "SELECT * FROM emails.calculate_email_analytics_grouped($1);"
    client = Tortoise.get_connection('default')
    rows = await client.execute_query(query, [group_by_factor])
    return [
        {
            "group_number": row["group_number"],
            "esp_provider": row["esp_provider"],
            "emails_received": row["emails_received"],
            "emails_sent": row["emails_sent"],
            "emails_rejected": row["emails_rejected"],
            "emails_delivered": row["emails_delivered"],
            "emails_opened": row["emails_opened"],
            "emails_bounced": row["emails_bounced"],
            "emails_complaint": row["emails_complaint"],
            "emails_replied": row["emails_replied"],
            "emails_failed": row["emails_failed"],
        }
        for row in rows[1]
    ]
