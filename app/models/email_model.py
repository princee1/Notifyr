from typing import Any, List, Literal, Optional, Self
from pydantic import BaseModel, model_validator
from enum import Enum
from tortoise import fields, models
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

    @model_validator(mode="after")
    def meta_validator(self)->Self:
        self.Disposition_Notification_To = None
        self.Return_Receipt_To = None
        return self


class EmailTemplateModel(BaseModel):
    meta: EmailMetaModel
    data: dict[str, Any]
    attachments: Optional[dict[str, Any]] = {}

class CustomEmailModel(BaseModel):
    meta: EmailMetaModel
    text_content: str
    html_content: str
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


class EmailTrackingORM(models.Model):
    email_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    message_id = fields.CharField(max_length=150, unique=True)
    recipient = fields.CharField(max_length=100)
    date_sent = fields.DatetimeField(auto_now_add=True)
    last_update = fields.DatetimeField(auto_now=True)
    expired_tracking_date = fields.DatetimeField(null=True)
    email_current_status = fields.CharField(max_length=50, null=True)
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
            "date_sent": self.date_sent.isoformat(),
            "last_update": self.last_update.isoformat(),
            "expired_tracking_date": self.expired_tracking_date.isoformat() if self.expired_tracking_date else None,
            "email_current_status": self.email_current_status,
            "spam_label": self.spam_label,
            "spam_detection_confidence": self.spam_detection_confidence
        }

class TrackingEventORM(models.Model):
    event_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    email = fields.ForeignKeyField("models.EmailTrackingORM", related_name="events", on_delete=fields.CASCADE)
    current_event = fields.CharField(max_length=50)
    date_event_received = fields.DatetimeField(auto_now_add=True)

    class Meta:
        schema = SCHEMA
        table = "trackingevent"

    @property
    def to_json(self):
        return {
            "event_id": str(self.event_id),
            "email_id": str(self.email_id),
            "current_event": self.current_event,
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

