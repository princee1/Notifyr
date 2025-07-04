from datetime import datetime,timedelta
from typing import Self
from urllib.parse import urlparse
from tortoise import Tortoise, fields, models
from app.utils.helper import uuid_v1_mc,generateId
from tortoise.contrib.pydantic import pydantic_model_creator
from pydantic import BaseModel, field_validator, model_validator
from app.utils.validation import url_validator

SCHEMA = 'links'

class LinkORM(models.Model):
    link_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    link_name = fields.CharField(max_length=100, unique=True)
    link_short_id = fields.CharField(max_length=20, unique=True, default=lambda: generateId(5))
    link_url = fields.CharField(max_length=150, unique=True)
    expiration = fields.DatetimeField(null=True)
    expiration_verification = fields.DatetimeField(null=True)
    total_visit_count = fields.IntField(default=0)
    public = fields.BooleanField(default=True)
    converted_count = fields.IntField(default=0,null=True)
    total_session_count = fields.IntField(default=0,null=True)
    # ownership_public_key = fields.TextField()
    # ownership_private_key = fields.TextField()
    ownership_signature = fields.TextField()
    ownership_nonce = fields.CharField(max_length=50, null=True)
    verified = fields.BooleanField(default=False)
    archived = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True,use_tz=True)
    updated_at = fields.DatetimeField(auto_now=True,use_tz=True)


    class Meta:
        schema = SCHEMA
        table = "link"

    @property
    def to_json(self):
        return {
            "link_id": str(self.link_id),
            "link_name": self.link_name,
            "link_short_id": self.link_short_id,
            "link_url": self.link_url,
            "expiration": self.expiration.isoformat() if self.expiration else None,
            "expiration_verification": self.expiration_verification.isoformat() if self.expiration_verification else None,
            "total_visit_count": self.total_visit_count,
            "converted_count":self.converted_count,
            "total_session_count":self.total_session_count,
            "public": self.public,
            "verified": self.verified,
            "archived": self.archived
        }

class LinkEventORM(models.Model):
    event_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    link = fields.ForeignKeyField("models.LinkORM", related_name="events", on_delete=fields.CASCADE)
    contact_id = fields.UUIDField(null=True)
    email_id = fields.UUIDField(null=True)
    user_agent = fields.CharField(max_length=150, null=True)
    #ip_address = fields.CharField(max_length=50, null=True)
    geo_lat = fields.FloatField(null=True)
    geo_long = fields.FloatField(null=True)
    country = fields.CharField(max_length=60, null=True)
    region = fields.CharField(max_length=60, null=True)
    referrer =  fields.CharField(max_length=100, null=True)
    timezone= fields.CharField(max_length=80, null=True)
    city = fields.CharField(max_length=100, null=True)
    date_clicked = fields.DatetimeField(auto_now_add=True)
    expiring_date = fields.DatetimeField(null=True)

    class Meta:
        schema = SCHEMA
        table = "linkevent"

    @property
    def to_json(self):
        return {
            "event_id": str(self.event_id),
            "link_id": str(self.link_id),
            "contact_id": str(self.contact_id) if self.contact_id else None,
            "email_id": str(self.email_id) if self.email_id else None,
            "user_agent": self.user_agent,
            #"ip_address": self.ip_address,
            "geo_lat": self.geo_lat,
            "geo_long": self.geo_long,
            "country": self.country,
            'region':self.region,
            "referrer":self.referrer,
            "timezone":self.timezone,
            "city": self.city,
            "date_clicked": self.date_clicked.isoformat(),
            "expiring_date": self.expiring_date.isoformat() if self.expiring_date else None
        }

class LinkSessionORM(models.Model):
    session_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    contact_id = fields.UUIDField(null=True)
    link = fields.ForeignKeyField("models.LinkORM", related_name="sessions", on_delete=fields.CASCADE)
    converted = fields.BooleanField(null=True)

    class Meta:
        schema = SCHEMA
        table = "linksession"

    @property
    def to_json(self):
        return {
            "session_id": str(self.session_id),
            "contact_id": str(self.contact_id) if self.contact_id else None,
            "link_id": str(self.link_id),
            "converted": self.converted
        }
    

class LinkAnalyticsORM(models.Model):
    link = fields.ForeignKeyField("models.LinkORM", related_name="analytics", on_delete=fields.CASCADE)
    day_start_date = fields.DateField(default=datetime.utcnow().date)
    visits_counts = fields.IntField(default=1)
    country = fields.CharField(max_length=60, null=True)
    region = fields.CharField(max_length=60, null=True)
    city = fields.CharField(max_length=100, null=True)
    device = fields.CharField(max_length=50, default="unknown")

    class Meta:
        schema = SCHEMA
        table = "linkanalytics"
        unique_together = ("link", "date_start_date", "country", "region", "city", "device")

    @property
    def to_json(self):
        return {
            "link_id": str(self.link_id),
            "day_start_date": self.day_start_date.isoformat(),
            "visits_counts": self.visits_counts,
            "country": self.country,
            "region": self.region,
            "city": self.city,
            "device": self.device,
        }

LinkModelBase = pydantic_model_creator(LinkORM,name="LinkORM",include=('link_url','expiration','link_name','public'))

class LinkModel(LinkModelBase):
    link_url:str
    expiration: datetime | None | float | int = None

    @field_validator('link_name')
    def check_link_name(cls, link_name):
        if not link_name:
            raise ValueError('Link name cannot be empty.')

        if len(link_name) >= 200:
            raise ValueError('Link name must be less than 200 characters.')
    
        return link_name

    @field_validator('expiration')
    def check_expiration(cls,expiration):
        if isinstance(expiration,(float,int)):
            if expiration<0:
                raise ValueError('Expiration cannot be negative')
            if expiration==0:
                return None
        return expiration
               
    @field_validator('link_url')
    def check_url(cls,link_url:str):
        if not url_validator(link_url):
            raise ValueError('url domain format not valid')
        # if urlparse(link_url).scheme != 'https':
        #     raise ValueError('domain must be hosted')
        return link_url
    

class UpdateLinkModel(LinkModel):

    archived:bool| None = None
    link_name:str |None =None
    expiration: datetime | None | float | int = None

    @field_validator("link_name")
    def check_link_name(cls, link_name):
        if link_name==None:
            return None
        return super().check_link_name(link_name)


    @field_validator("link_url")
    def check_url(cls, link_url):
        return None

    @model_validator(mode="after")
    def check_model(self) -> Self:
        self.link_url = None
        self.public = None

        if self.expiration is None and self.link_name is None and self.archived is None:
            raise ValueError("At least one of 'expiration', 'link_name', or 'archived' must be provided.")

        return self

    @field_validator('expiration')
    def check_expiration(cls,expiration):
        if  expiration == None:
            return None
        return super().check_expiration(expiration)

class QRCodeModel(BaseModel):
    version: int = 1
    box_size: int = 10
    border: int = 4


async def bulk_upsert_analytics(analytics_values: dict[str, dict]):
    """
    Bulk upsert link analytics data.

    Args:
        data (dict): A dictionary containing analytics data.
    """
    query = """
    SELECT links.bulk_upsert_analytics($1);
    """
    client = Tortoise.get_connection('default')
    await client.execute_query(query, [analytics_values])


async def bulk_upsert_links_vc(links_values: dict[str, int]):
    """
    Bulk upsert link visit counts.

    Args:
        data (dict): A dictionary containing link visit counts.
    """
    query = """
    SELECT links.bulk_upsert_links_visits_counts($1);
    """
    client = Tortoise.get_connection('default')
    await client.execute_query(query, [links_values])


async def fetch_analytics_sorted_by_date():
    """
    Fetches all analytics sorted by date from the oldest to the newest.

    Returns:
        dict: Contains metadata and list of analytics data sorted by date.
    """
    query = "SELECT * FROM links.FetchAnalyticsByDate();"
    client = Tortoise.get_connection('default')
    rows = await client.execute_query(query, [])

    column_names = ["link_id", "day_start_date", "country", "region", "city", "device", "visits_counts"]

    # analytics_data = [
    #     {
    #         "link_id": row[0],
    #         "day_start_date": row[1],
    #         "country": row[2],
    #         "region": row[3],
    #         "city": row[4],
    #         "device": row[5],
    #         "visits_counts": row[6],
    #     }
    #     for row in rows[1]
    # ]

    return {
        "metadata": {
            "total_records": len(rows),
            "sorted_by": "date",
            "order": "ascending",
            "columns": column_names
        },
        "data": rows
    }