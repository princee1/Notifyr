from enum import Enum
from datetime import datetime
from typing import Self, TypedDict
from tortoise import Tortoise, fields, models
from app.utils.helper import uuid_v1_mc
from tortoise.contrib.pydantic import pydantic_model_creator
from pydantic import BaseModel, field_validator, model_validator

SCHEMA = 'twilio'

# Define Enums
class SMSStatusEnum(str, Enum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    RECEIVED = "RECEIVED"
    BOUNCE = "BOUNCE"

class CallStatusEnum(str, Enum):
    RECEIVED = "RECEIVED"
    COMPLETED = "COMPLETED"
    NO_ANSWER = "NO-ANSWER"
    INITIATED = "INITIATED"
    RINGING = "RINGING"
    ANSWERED = "ANSWERED"
    FAILED = 'FAILED'
    SENT = "SENT"
    BOUNCE = "BOUNCE"



class DirectionEnum(str, Enum):
    INBOUND = "I"
    OUTBOUND = "O"

class SMSTrackingORM(models.Model):
    sms_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    sms_sid = fields.CharField(max_length=60,null=True,default=None)
    contact = fields.ForeignKeyField('models.ContactORM',null=True,on_delete=fields.NO_ACTION)
    recipient = fields.CharField(max_length=100)
    sender = fields.CharField(max_length=100)
    date_sent = fields.DatetimeField(auto_now_add=True, use_tz=True)
    last_update = fields.DatetimeField(auto_now=True, use_tz=True)
    expired_tracking_date = fields.DatetimeField(null=True)
    sms_current_status = fields.CharEnumField(enum_type=SMSStatusEnum, max_length=50)
    
    class Meta:
        schema = SCHEMA
        table = "smstracking"

    @property
    def to_json(self):
        return {
            "sms_id": str(self.sms_id),
            "sms_sid":self.sms_sid,
            "recipient": self.recipient,
            "contact_id": str(self.contact.contact_id) if self.contact != None else None,
            "sender": self.sender,
            "date_sent": self.date_sent.isoformat(),
            "last_update": self.last_update.isoformat(),
            "expired_tracking_date": self.expired_tracking_date.isoformat() if self.expired_tracking_date else None,
            "sms_current_status": self.sms_current_status.value,
        }


class CallTrackingORM(models.Model):
    call_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    call_sid = fields.CharField(max_length=60,null=False,default=None)
    contact = fields.ForeignKeyField('models.ContactORM',null=True,on_delete=fields.NO_ACTION)
    recipient = fields.CharField(max_length=100)
    sender = fields.CharField(max_length=100)
    date_started = fields.DatetimeField(auto_now_add=True, use_tz=True)
    last_update = fields.DatetimeField(auto_now=True, use_tz=True)
    expired_tracking_date = fields.DatetimeField(null=True)
    call_current_status = fields.CharEnumField(enum_type=CallStatusEnum, max_length=50)

    class Meta:
        schema = SCHEMA
        table = "calltracking"

    @property
    def to_json(self):
        return {
            "call_id": str(self.call_id),
            "call_sid": self.call_sid,
            "contact_id": str(self.contact.contact_id) if self.contact != None else None,
            "recipient": self.recipient,
            "sender": self.sender,
            "date_started": self.date_started.isoformat(),
            "last_update": self.last_update.isoformat(),
            "expired_tracking_date": self.expired_tracking_date.isoformat() if self.expired_tracking_date else None,
            "call_current_status": self.call_current_status.value,
        }


class SMSEventORM(models.Model):
    event_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    sms = fields.ForeignKeyField("models.SMSTrackingORM", related_name="events", on_delete=fields.CASCADE)
    sms_sid = fields.CharField(max_length=60,null=False)
    direction = fields.CharEnumField(enum_type=DirectionEnum, max_length=1)
    current_event = fields.CharEnumField(enum_type=SMSStatusEnum, max_length=50)
    description = fields.CharField(max_length=200, null=True)
    date_event_received = fields.DatetimeField(auto_now_add=True, use_tz=True)

    class JSON(TypedDict):
        event_id:str
        sms_id:str
        sms_sid:str
        direction:str
        current_event:str
        description:str
        date_event_received:str
        correction:bool = False

    class Meta:
        schema = SCHEMA
        table = "smsevent"

    @property
    def to_json(self):
        return {
            "event_id": str(self.event_id),
            "sms_id": str(self.sms_id),
            "sms_sid":self.sms_sid,
            "direction": self.direction.value,
            "current_event": self.current_event.value,
            "description": self.description,
            "date_event_received": self.date_event_received.isoformat(),
        }


class CallEventORM(models.Model):
    event_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    call = fields.ForeignKeyField("models.CallTrackingORM", related_name="events", null=True, on_delete=fields.CASCADE)
    call_sid = fields.CharField(max_length=60,null=False)
    direction = fields.CharEnumField(enum_type=DirectionEnum, max_length=1)
    current_event = fields.CharEnumField(enum_type=CallStatusEnum, max_length=50)
    description = fields.CharField(max_length=200, null=True)
    country = fields.CharField(max_length=100, null=True)
    state = fields.CharField(max_length=100, null=True)
    city = fields.CharField(max_length=100, null=True)
    date_event_received = fields.DatetimeField(auto_now_add=True, use_tz=True)

    
    class JSON(TypedDict):
        event_id:str
        call_id:str
        call_sid:str
        direction:str
        current_event:str
        description:str
        country:str
        city:str
        state:str
        date_event_received:str
        correction:bool = False

    class Meta:
        schema = SCHEMA
        table = "callevent"

    @property
    def to_json(self):
        return {
            "event_id": str(self.event_id),
            "call_id": str(self.call.call_id) if self.call != None else None,
            "call_sid": self.call_sid,
            "direction": self.direction.value,
            "current_event": self.current_event.value,
            "description": self.description,
            "country": self.country,
            "state": self.state,
            "city": self.city,
            "date_event_received": self.date_event_received.isoformat(),
        }


class SMSAnalyticsORM(models.Model):
    analytics_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    week_start_date = fields.DateField(default=datetime.utcnow().date)
    direction = fields.CharEnumField(enum_type=DirectionEnum, max_length=1)
    sms_sent = fields.IntField(default=0)
    sms_delivered = fields.IntField(default=0)
    sms_failed = fields.IntField(default=0)
    sms_bounce = fields.IntField(default=0)  # Added sms_bounce field
    total_price = fields.FloatField(default=0)
    average_price = fields.FloatField(default=0)

    class Meta:
        schema = SCHEMA
        table = "smsanalytics"
        unique_together = ("week_start_date", "direction")

    @property
    def to_json(self):
        return {
            "analytics_id": str(self.analytics_id),
            "week_start_date": self.week_start_date.isoformat(),
            "direction": self.direction.value,
            "sms_sent": self.sms_sent,
            "sms_delivered": self.sms_delivered,
            "sms_failed": self.sms_failed,
            "sms_bounce": self.sms_bounce,  # Added sms_bounce
            "total_price": self.total_price,
            "average_price": self.average_price,
        }


class CallAnalyticsORM(models.Model):
    analytics_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    week_start_date = fields.DateField(default=datetime.utcnow().date)
    direction = fields.CharEnumField(enum_type=DirectionEnum, max_length=1)
    country = fields.CharField(max_length=100, null=True)
    state = fields.CharField(max_length=100, null=True)
    city = fields.CharField(max_length=100, null=True)
    calls_started = fields.IntField(default=0)
    calls_completed = fields.IntField(default=0)
    calls_failed = fields.IntField(default=0)
    calls_not_answered = fields.IntField(default=0)  # Added calls_not_answered field
    calls_bounce = fields.IntField(default=0)  # Added calls_bounce field
    total_price = fields.FloatField(default=0)
    average_price = fields.FloatField(default=0)
    total_duration = fields.IntField(default=0)
    average_duration = fields.FloatField(default=0)
    total_call_duration = fields.IntField(default=0)
    average_call_duration = fields.FloatField(default=0)

    class Meta:
        schema = SCHEMA
        table = "callanalytics"
        unique_together = ("week_start_date", "direction", "country", "state", "city")

    @property
    def to_json(self):
        return {
            "analytics_id": str(self.analytics_id),
            "week_start_date": self.week_start_date.isoformat(),
            "direction": self.direction.value,
            "country": self.country,
            "state": self.state,
            "city": self.city,
            "calls_started": self.calls_started,
            "calls_completed": self.calls_completed,
            "calls_failed": self.calls_failed,
            "calls_not_answered": self.calls_not_answered,  # Added calls_not_answered
            "calls_bounce": self.calls_bounce,  # Added calls_bounce
            "total_price": self.total_price,
            "average_price": self.average_price,
            "total_duration": self.total_duration,
            "average_duration": self.average_duration,
            "total_call_duration": self.total_call_duration,
            "average_call_duration": self.average_call_duration,
            "ringing_duration": self.total_call_duration - self.total_duration
        }


async def bulk_upsert_call_analytics(analytics_data):
    values_str = ", ".join(
        f"ROW('{direction}', '{country}', '{state}', '{city}', '{calls_started}', '{calls_completed}', '{calls_failed}', '{calls_not_answered}', '{total_price}', '{average_price}', '{total_duration}', '{average_duration}', '{total_call_duration}', '{average_call_duration}')"
        for direction, country, state, city, calls_started, calls_completed, calls_failed, calls_not_answered, total_price, average_price, total_duration, average_duration, total_call_duration, average_call_duration in analytics_data
    )
    query = f"SELECT * FROM twilio.bulk_upsert_call_analytics($1)"
    client = Tortoise.get_connection('default')
    return await client.execute_query(query, [f"ARRAY[{values_str}]"])

async def bulk_upsert_sms_analytics(analytics_data):
    values_str = ", ".join(
        f"ROW('{direction}', '{sms_sent}', '{sms_delivered}', '{sms_failed}', '{total_price}', '{average_price}')"
        for direction, sms_sent, sms_delivered, sms_failed, total_price, average_price in analytics_data
    )
    query = f"SELECT * FROM twilio.bulk_upsert_sms_analytics($1)"
    client = Tortoise.get_connection('default')
    return await client.execute_query(query, [f"ARRAY[{values_str}]"])


async def aggregate_sms_analytics(group_by_factor: int):
    query = """
        SELECT * FROM twilio.calculate_sms_analytics_grouped($1)
    """
    client = Tortoise.get_connection('default')
    return await client.execute_query(query, [group_by_factor])

async def aggregate_call_analytics(group_by_factor: int):
    query = """
        SELECT * FROM twilio.calculate_call_analytics_grouped($1)
    """
    client = Tortoise.get_connection('default')
    return await client.execute_query(query, [group_by_factor])

async def fetch_call_analytics_by_week():
    """
    Fetches all call analytics sorted by week from the oldest to the newest.

    Returns:
        dict: Contains metadata and list of call analytics data sorted by week.
    """
    query = "SELECT * FROM twilio.FetchCallAnalyticsByWeek;"
    client = Tortoise.get_connection('default')
    rows = await client.execute_query(query, [])

    column_names = [
        "analytics_id", "week_start_date", "direction", "country", "state", "city",
        "calls_started", "calls_completed", "calls_failed", "total_price", "average_price",
        "total_duration", "average_duration"
    ]

    return {
        "metadata": {
            "total_records": len(rows),
            "sorted_by": "week_start_date",
            "order": "ascending",
            "columns": column_names
        },
        "data": rows
    }