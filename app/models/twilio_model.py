from datetime import datetime
from typing import Self
from tortoise import Tortoise, fields, models
from app.utils.helper import uuid_v1_mc
from tortoise.contrib.pydantic import pydantic_model_creator
from pydantic import BaseModel, field_validator, model_validator


SCHEMA = 'twilio'

class SMSTrackingORM(models.Model):
    sms_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    message_sid = fields.CharField(max_length=150, unique=True)
    recipient = fields.CharField(max_length=100)
    sender = fields.CharField(max_length=100)
    date_sent = fields.DatetimeField(auto_now_add=True, use_tz=True)
    last_update = fields.DatetimeField(auto_now=True, use_tz=True)
    expired_tracking_date = fields.DatetimeField(null=True)
    sms_current_status = fields.CharEnumField(
        enum_type=["QUEUED", "SENT", "DELIVERED", "FAILED", "RECEIVED"], max_length=50
    )
    price = fields.FloatField(null=True)
    price_unit = fields.CharField(max_length=10, null=True)

    class Meta:
        schema = SCHEMA
        table = "smstracking"

    @property
    def to_json(self):
        return {
            "sms_id": str(self.sms_id),
            "message_sid": self.message_sid,
            "recipient": self.recipient,
            "sender": self.sender,
            "date_sent": self.date_sent.isoformat(),
            "last_update": self.last_update.isoformat(),
            "expired_tracking_date": self.expired_tracking_date.isoformat() if self.expired_tracking_date else None,
            "sms_current_status": self.sms_current_status,
            "price": self.price,
            "price_unit": self.price_unit,
        }


class CallTrackingORM(models.Model):
    call_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    call_sid = fields.CharField(max_length=150, unique=True)
    recipient = fields.CharField(max_length=100)
    sender = fields.CharField(max_length=100)
    date_started = fields.DatetimeField(auto_now_add=True, use_tz=True)
    last_update = fields.DatetimeField(auto_now=True, use_tz=True)
    expired_tracking_date = fields.DatetimeField(null=True)
    call_current_status = fields.CharEnumField(
        enum_type=["RECEIVED", "COMPLETED", "NO-ANSWER", "RINGING", "ANSWERED"], max_length=50
    )
    duration = fields.IntField(null=True)
    price = fields.FloatField(null=True)
    price_unit = fields.CharField(max_length=10, null=True)

    class Meta:
        schema = SCHEMA
        table = "calltracking"

    @property
    def to_json(self):
        return {
            "call_id": str(self.call_id),
            "call_sid": self.call_sid,
            "recipient": self.recipient,
            "sender": self.sender,
            "date_started": self.date_started.isoformat(),
            "last_update": self.last_update.isoformat(),
            "expired_tracking_date": self.expired_tracking_date.isoformat() if self.expired_tracking_date else None,
            "call_current_status": self.call_current_status,
            "duration": self.duration,
            "price": self.price,
            "price_unit": self.price_unit,
        }


class SMSEventORM(models.Model):
    event_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    sms = fields.ForeignKeyField("models.SMSTrackingORM", related_name="events", on_delete=fields.CASCADE)
    direction = fields.CharEnumField(enum_type=["I", "O"], max_length=1)
    current_event = fields.CharEnumField(
        enum_type=["QUEUED", "SENT", "DELIVERED", "FAILED", "RECEIVED"], max_length=50
    )
    description = fields.CharField(max_length=200, null=True)
    date_event_received = fields.DatetimeField(auto_now_add=True, use_tz=True)

    class Meta:
        schema = SCHEMA
        table = "smsevent"

    @property
    def to_json(self):
        return {
            "event_id": str(self.event_id),
            "sms_id": str(self.sms_id),
            "direction": self.direction,
            "current_event": self.current_event,
            "description": self.description,
            "date_event_received": self.date_event_received.isoformat(),
        }


class CallEventORM(models.Model):
    event_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    call = fields.ForeignKeyField("models.CallTrackingORM", related_name="events", on_delete=fields.CASCADE)
    direction = fields.CharEnumField(enum_type=["I", "O"], max_length=1)
    current_event = fields.CharEnumField(
        enum_type=["RECEIVED", "COMPLETED", "NO-ANSWER", "RINGING", "ANSWERED"], max_length=50
    )
    description = fields.CharField(max_length=200, null=True)
    country = fields.CharField(max_length=100, null=True)
    state = fields.CharField(max_length=100, null=True)
    city = fields.CharField(max_length=100, null=True)
    date_event_received = fields.DatetimeField(auto_now_add=True, use_tz=True)

    class Meta:
        schema = SCHEMA
        table = "callevent"

    @property
    def to_json(self):
        return {
            "event_id": str(self.event_id),
            "call_id": str(self.call_id),
            "direction": self.direction,
            "current_event": self.current_event,
            "description": self.description,
            "country": self.country,
            "state": self.state,
            "city": self.city,
            "date_event_received": self.date_event_received.isoformat(),
        }


class SMSAnalyticsORM(models.Model):
    analytics_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    week_start_date = fields.DateField(default=datetime.utcnow().date)
    direction = fields.CharEnumField(enum_type=["I", "O"], max_length=1)
    sms_sent = fields.IntField(default=0)
    sms_delivered = fields.IntField(default=0)
    sms_failed = fields.IntField(default=0)
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
            "direction": self.direction,
            "sms_sent": self.sms_sent,
            "sms_delivered": self.sms_delivered,
            "sms_failed": self.sms_failed,
            "total_price": self.total_price,
            "average_price": self.average_price,
        }


class CallAnalyticsORM(models.Model):
    analytics_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    week_start_date = fields.DateField(default=datetime.utcnow().date)
    direction = fields.CharEnumField(enum_type=["I", "O"], max_length=1)
    country = fields.CharField(max_length=100, null=True)
    state = fields.CharField(max_length=100, null=True)
    city = fields.CharField(max_length=100, null=True)
    calls_started = fields.IntField(default=0)
    calls_completed = fields.IntField(default=0)
    calls_failed = fields.IntField(default=0)
    total_price = fields.FloatField(default=0)
    average_price = fields.FloatField(default=0)
    total_duration = fields.IntField(default=0)
    average_duration = fields.FloatField(default=0)

    class Meta:
        schema = SCHEMA
        table = "callanalytics"
        unique_together = ("week_start_date", "direction", "country", "state", "city")

    @property
    def to_json(self):
        return {
            "analytics_id": str(self.analytics_id),
            "week_start_date": self.week_start_date.isoformat(),
            "direction": self.direction,
            "country": self.country,
            "state": self.state,
            "city": self.city,
            "calls_started": self.calls_started,
            "calls_completed": self.calls_completed,
            "calls_failed": self.calls_failed,
            "total_price": self.total_price,
            "average_price": self.average_price,
            "total_duration": self.total_duration,
            "average_duration": self.average_duration,
        }


async def bulk_upsert_call_analytics(analytics_data):
    values_str = ", ".join(
        f"ROW('{week_start_date}', '{direction}', '{country}', '{state}', '{city}', '{calls_started}', '{calls_completed}', '{calls_failed}', '{total_price}', '{average_price}', '{total_duration}', '{average_duration}')::twilio.call_analytics_input"
        for week_start_date, direction, country, state, city, calls_started, calls_completed, calls_failed, total_price, average_price, total_duration, average_duration in analytics_data
    )
    query = f"SELECT * FROM twilio.bulk_upsert_call_analytics($1)"
    client = Tortoise.get_connection('default')
    return await client.execute_query(query, [f"ARRAY[{values_str}]"])

async def bulk_upsert_sms_analytics(analytics_data):
    values_str = ", ".join(
        f"ROW('{week_start_date}', '{direction}', '{sms_sent}', '{sms_delivered}', '{sms_failed}', '{total_price}', '{average_price}')::twilio.sms_analytics_input"
        for week_start_date, direction, sms_sent, sms_delivered, sms_failed, total_price, average_price in analytics_data
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