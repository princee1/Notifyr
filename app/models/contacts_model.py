from tortoise import fields
from tortoise.models import Model


class ContactModel(Model):
    id = fields.IntField(pk=True)
    first_name = fields.CharField(max_length=255)
    last_name = fields.CharField(max_length=255)
    email = fields.CharField(max_length=255, null=False, unique=True)
    phone = fields.CharField(max_length=255, null=False, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    def __str__(self):
        return self.full_name
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class SecurityContactModel(Model):
    security_id = fields.IntField(pk=True)
    contact_id = fields.ForeignKeyField('models.ContactModel', related_name='security_contacts')    
    security_code = fields.TextField()
    security_phrase = fields.TextField()
    voice_embeddings = fields.JSONField([list[float]])
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    def __str__(self):
        return f"{self.security_id} {self.contact_id}"
