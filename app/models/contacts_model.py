from enum import Enum
from tortoise import fields
from tortoise.models import Model
import uuid
from pydantic import BaseModel, field_validator,model_validator
from typing_extensions import Literal, Self
from app.utils.helper import phone_parser
from app.utils.validation import email_validator, phone_number_validator
from app.definition._error import BaseError
from tortoise import Tortoise

class Frequency(Enum):
    weekly = 'weekly'
    bi_weekly= 'bi_weekly'
    monthly = 'monthly'
    always = 'always'

class Status(Enum):
    Active = 'Active'
    Pending = 'Pending'
    Blacklist = 'Blacklist'
    Inactive = 'Inactive'

class Lang(Enum):
    fr='fr'
    en='en'

class ContentType(Enum):
    newsletter = 'newsletter'
    event = 'event'
    notification = 'notification'
    promotion = 'promotion'
    update = 'update'
    other = 'other'



##################################################################              ##############################################################3333333333

class ContactNotExistsError(BaseError):
    ...
class ContactAlreadyExistsError(BaseError):
    
    def __init__(self,email,phone ,*args):
        self.email=email
        self.phone=phone
        super().__init__(*args)
    
    @property
    def message(self):
        if self.email and self.phone:
            return "Both the email and the phone field is already used"

        if self.email:
            return "The email field is already used"
        
        return "The phone field is already used"

class ContactOptInCodeNotMatchError(BaseError):
    ...

class ContactDoubleOptInAlreadySetError(BaseError):
    ...

##################################################################              ##############################################################3333333333

CONTACTS_SCHEMA = "contacts"

def table_builder (name:str):
    return name
    return f"{CONTACTS_SCHEMA}.{name}"


class ContactORM(Model):
    contact_id = fields.UUIDField(pk=True, default=uuid.uuid4)
    first_name = fields.CharField(max_length=50)
    last_name = fields.CharField(max_length=50)
    email = fields.CharField(max_length=50, null=True, unique=True)
    phone = fields.CharField(max_length=50, null=True, unique=True)
    app_registered = fields.BooleanField(default=False)
    opt_in_code= fields.IntField(unique=True, null=True)
    auth_token = fields.TextField(null=True)
    frequency = fields.CharEnumField(max_length=20,enum_type=Frequency,default=Frequency.always)
    action_code = fields.TextField(null=True)
    status = fields.CharEnumField(max_length=20,enum_type=Status,default=Status.Active)
    lang = fields.CharField(max_length=20,default="en")
    created_at = fields.DatetimeField(auto_now=True,use_tz=True)
    updated_at = fields.DatetimeField(auto_now=True,use_tz=True)

    def __str__(self):
        return self.full_name
    
    @property
    def to_json(self):
        return {
        'contact_id': str(self.contact_id),
        'first_name': self.first_name,
        'last_name': self.last_name,
        'email': self.email,
        'phone': self.phone,
        'app_registered': self.app_registered,
        'lang': self.lang,
        'created_at': self.created_at.isoformat(),
    }

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        schema = CONTACTS_SCHEMA
        table = table_builder("contact")


class SecurityContactORM(Model):
    security_id = fields.UUIDField(pk=True, default=uuid.uuid4)
    contact = fields.ForeignKeyField('models.ContactORM', related_name='security_contacts', on_delete=fields.CASCADE, on_update=fields.CASCADE)
    security_code = fields.TextField(null=True)
    security_code_salt = fields.CharField(64,null=True)
    security_phrase = fields.TextField(null=True)
    security_phrase_salt = fields.CharField(64,null=True)
    voice_embedding = fields.TextField(null=True)
    voice_embedding_salt = fields.CharField(64,null=True)
    created_at = fields.DatetimeField(auto_now_add=True,use_tz=True)
    updated_at = fields.DatetimeField(auto_now=True,use_tz=True)

    def __str__(self):
        return f"{self.security_id} {self.contact}"

    class Meta:
        schema = CONTACTS_SCHEMA
        table = table_builder("securitycontact")

class SubscriptionContactStatusORM(Model):
    subscription_id = fields.UUIDField(pk=True, default=uuid.uuid4)
    contact = fields.ForeignKeyField('models.ContactORM', related_name='subscriptions_status', unique=True,on_delete=fields.CASCADE, on_update=fields.CASCADE)
    email_status = fields.CharField(max_length=20)
    sms_status = fields.CharField(max_length=20)
    created_at = fields.DatetimeField(auto_now_add=True,use_tz=True)
    updated_at = fields.DatetimeField(auto_now=True,use_tz=True)

    def __str__(self):
        return f"{self.subscription_id} {self.contact}"

    class Meta:
        table = table_builder("subscriptioncontact")
        schema = CONTACTS_SCHEMA


class Reason(Model):
    reason_id = fields.UUIDField(pk=True, default=uuid.uuid4)
    reason_description = fields.TextField(null=True)
    reason_name = fields.CharField(max_length=255, unique=True)
    reason_count = fields.BigIntField(default=0)

    class Meta:
        table = "reason"
        schema = CONTACTS_SCHEMA

class SubsContentORM(Model):
    content_id = fields.UUIDField(pk=True, default=uuid.uuid4)
    content_name = fields.CharField(max_length=50, unique=True)
    content_description = fields.TextField(null=True)
    content_type = fields.CharEnumField(max_length=20,enum_type=ContentType)

    class Meta:
        table = "subscontent"
        schema = CONTACTS_SCHEMA

class Subscription(Model):
    subs_id = fields.UUIDField(pk=True, default=uuid.uuid4)
    contact = fields.ForeignKeyField('models.ContactORM', related_name='subscription', on_delete=fields.CASCADE, on_update=fields.CASCADE)
    content = fields.ForeignKeyField('models.SubsContentORM', related_name='content', on_delete=fields.CASCADE, on_update=fields.CASCADE)
    subs_status = fields.CharEnumField(max_length=20, enum_type=Status, default=Status.Active)
    created_at = fields.DatetimeField(auto_now_add=True, use_tz=True)
    updated_at = fields.DatetimeField(auto_now=True, use_tz=True)

    class Meta:
        table = "subscription"
        schema = CONTACTS_SCHEMA
        unique_together = (("contact", "content"),)


class ContentTypeSubscriptionORM(Model):
    contact = fields.ForeignKeyField('models.ContactORM', related_name='content_type_subs', on_delete=fields.CASCADE, on_update=fields.CASCADE)
    event = fields.BooleanField(default=False)
    newsletter = fields.BooleanField(default=False)
    promotion= fields.BooleanField(default=False)
    other = fields.BooleanField(default =True)
    created_at = fields.DatetimeField(auto_now_add=True, use_tz=True)
    updated_at = fields.DatetimeField(auto_now=True, use_tz=True)


    class Meta:
        table = "contenttypesubscription"
        schema = CONTACTS_SCHEMA

##################################################################              ##############################################################3333333333


class SubscriptionStatusModel(BaseModel):
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

class ContentTypeSubsModel(BaseModel):
    event:bool |None = None
    newsletter:bool|None =None
    promotion:bool|None = None
    other:bool |None = None
    subscription_status:SubscriptionStatusModel |None =None

    @model_validator(mode="after")
    def check_flag(self,):
        if self.event == None and self.newsletter == None and self.promotion== None and self.other == None and self.subscription_status==None:
            raise ValueError('Every values cannot all be false')
        return self

class ContactModel(BaseModel):
    first_name:str
    last_name:str
    email:str =None
    phone:str=None
    app_registered:bool
    lang:Lang
    frequency:Frequency

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

class SubsContentModel(BaseModel):
    ...


##################################################################              ##############################################################3333333333

def query(method:Literal['update','reset']): return f'SELECT {method}_reason($1::VARCHAR(50))'

async def reset_reason(name:str):
    q = query('reason')
    client = Tortoise.get_connection('default')
    await client.execute_query(q,[name])
    
async def update_reason(name:str):
    q = query('update')
    client = Tortoise.get_connection('default')
    await client.execute_query(q,[name])

async def get_contact_summary(contact_id: str):
    query = "SELECT * FROM contact_summary WHERE contact_id = $1::UUID"
    client = Tortoise.get_connection('default')
    result = await client.execute_query(query, [contact_id])
    return result[1][0] if result else None