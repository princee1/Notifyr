from tortoise import fields
from tortoise.models import Model
import uuid
from pydantic import BaseModel, field_validator,model_validator
from typing_extensions import Self
from app.utils.helper import phone_parser
from app.utils.validation import email_validator, phone_number_validator
from app.definition._error import BaseError


class ContactNotExistsError(BaseError):
    ...

class ContactAlreadyExistsError(BaseError):
    ...


CONTACTS_SCHEMA = "schema"

def table_builder (name:str):
    return f"{CONTACTS_SCHEMA}.{name}"


class ContactORM(Model):
    contact_id = fields.UUIDField(pk=True, default=uuid.uuid4)
    first_name = fields.CharField(max_length=50)
    last_name = fields.CharField(max_length=50)
    email = fields.CharField(max_length=50, null=False, unique=True)
    phone = fields.CharField(max_length=50, null=True, unique=True)
    app_registered = fields.BooleanField(default=False)
    lang = fields.CharField(max_length=15,default="en")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    def __str__(self):
        return self.full_name
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        table = table_builder("Contact")


class SecurityContactORM(Model):
    security_id = fields.UUIDField(pk=True, default=uuid.uuid4)
    contact_id = fields.ForeignKeyField('models.ContactModelORM', related_name='security_contacts', on_delete=fields.CASCADE, on_update=fields.CASCADE)
    security_code = fields.IntField()
    security_phrase = fields.TextField()
    voice_embeddings = fields.JSONField()
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    def __str__(self):
        return f"{self.security_id} {self.contact_id}"

    class Meta:
        table = table_builder("SecurityContact")

class SubscriptionORM(Model):
    subscription_id = fields.UUIDField(pk=True, default=uuid.uuid4)
    contact_id = fields.ForeignKeyField('models.ContactModelORM', related_name='subscriptions', unique=True)
    email_status = fields.CharField(max_length=20)
    sms_status = fields.CharField(max_length=20)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    def __str__(self):
        return f"{self.subscription_id} {self.contact_id}"

    class Meta:
        table = table_builder("SubscriptionContact")


class InfoModel(BaseModel):
    first_name:str
    last_name:str
    email:str =None
    phone:str=None
    app_registered:bool
    lang:str

    @field_validator('email')
    def  check_email(cls,email):
        if email == None:
            return None
        if not email_validator(email):
            raise ValueError('Value is not the correct email format')
        return email

    @field_validator('phone')
    def  check_phone(cls,phone):
        if phone == None:
            return None
        phone = phone_parser(phone)
        if not phone_number_validator(phone):
            raise ValueError("Value is not the correct phone format")
        return phone  

    @field_validator('lang')
    def  check_language(cls,lang):
        if lang not in ('en','fr'):
            raise ValueError('Value lang is not supported yet only en or fr')
        return lang

    @model_validator(mode="after")
    def check_email_phone(self)->Self:
        if self.phone ==None and self.email == None:
            raise ValueError("Email and phone cant be both null")
        return self

class SecurityModel(BaseModel):
    security_code:int
    security_phrase:str

    @field_validator('security_code')
    def  check_security_code(cls,security_code):
        if not (security_code >=100000 and  security_code<=999999):
            raise ValueError("Value is not a valid 6 digit format")
        return security_code

class SubscriptionModel(BaseModel):
    email_status:str=None
    sms_status:str=None

    @field_validator('email_status')
    def  check_lang(cls,email_status):
        if email_status == None:
            return None
        if email_status not in ('Active','Inactive'):
            raise ValueError('Suscription status is not valid: (Active or Inactive)')
        return email_status

    @field_validator('sms_status')
    def  check_lang(cls,sms_status):
        if sms_status ==None:
            return None
        if sms_status not in ('Active','Inactive'):
            raise ValueError('Suscription status is not valid (Active or Inactive)')
        return sms_status
    
    @model_validator(mode="after")
    def check_email_phone(self)->Self:
        if self.email_status ==None and self.sms_status == None:
            raise ValueError("Email status and phone status cant be both null")
        return self



class ContactModel(BaseModel):
    info:InfoModel
    security:SecurityModel
    subscription:SubscriptionModel