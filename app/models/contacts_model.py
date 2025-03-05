from tortoise import fields
from tortoise.models import Model
import uuid

CONTACTS_SCHEMA = "schema"

def table_builder (name:str):
    return f"{CONTACTS_SCHEMA}.{name}"


class ContactModel(Model):
    contact_id = fields.UUIDField(pk=True, default=uuid.uuid4)
    first_name = fields.CharField(max_length=50)
    last_name = fields.CharField(max_length=50)
    email = fields.CharField(max_length=50, null=False, unique=True)
    phone = fields.CharField(max_length=50, null=True, unique=True)
    app_registered = fields.BooleanField(default=False)
    lang = fields.CharField(max_length=15)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    def __str__(self):
        return self.full_name
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        table = table_builder("Contact")



class SecurityContactModel(Model):
    security_id = fields.UUIDField(pk=True, default=uuid.uuid4)
    contact_id = fields.ForeignKeyField('models.ContactModel', related_name='security_contacts', on_delete=fields.CASCADE, on_update=fields.CASCADE)
    security_code = fields.TextField()
    security_phrase = fields.TextField()
    voice_embeddings = fields.JSONField()
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    def __str__(self):
        return f"{self.security_id} {self.contact_id}"

    class Meta:
        table = table_builder("SecurityContact")

class SubscriptionModel(Model):
    subscription_id = fields.UUIDField(pk=True, default=uuid.uuid4)
    contact_id = fields.ForeignKeyField('models.ContactModel', related_name='subscriptions', unique=True)
    email_status = fields.CharField(max_length=20)
    sms_status = fields.CharField(max_length=20)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    def __str__(self):
        return f"{self.subscription_id} {self.contact_id}"

    class Meta:
        table = table_builder("SubscriptionContact")
