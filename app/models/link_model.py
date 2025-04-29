from tortoise import fields, models
from app.utils.helper import uuid_v1_mc

SCHEMA = 'links'

class LinkORM(models.Model):
    link_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    link_name = fields.CharField(max_length=100, unique=True)
    link_short_id = fields.CharField(max_length=20, unique=True)
    link_url = fields.CharField(max_length=150, unique=True)
    expiration = fields.DatetimeField(null=True)
    total_visit_count = fields.IntField(default=0)
    public = fields.BooleanField(default=True)
    verified = fields.BooleanField(default=False)
    archived = fields.BooleanField(default=False)

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
            "total_visit_count": self.total_visit_count,
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
    ip_address = fields.CharField(max_length=50, null=True)
    geo_lat = fields.FloatField(null=True)
    geo_long = fields.FloatField(null=True)
    country = fields.CharField(max_length=60, null=True)
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
            "ip_address": self.ip_address,
            "geo_lat": self.geo_lat,
            "geo_long": self.geo_long,
            "country": self.country,
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