from datetime import datetime
from enum import Enum
from typing import Optional, TypedDict
from tortoise import fields
from tortoise.models import Model
from pydantic import BaseModel, field_validator,model_validator
from typing_extensions import Literal, Self
from app.utils.helper import phone_parser
from app.utils.validation import email_validator, phone_number_validator
from app.definition._error import BaseError
from tortoise import Tortoise
from app.utils.helper import uuid_v1_mc


##################################################################              ##############################################################3333333333

class Relay(Enum):
    email="email"
    sms="sms"

class SubscriptionStatus(Enum):
    Active="Active"
    Inactive="Inactive"

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

CONTACTS_SCHEMA = "contacts"

def table_builder (name:str):
    return name
    return f"{CONTACTS_SCHEMA}.{name}"

class ContactORM(Model):
    contact_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
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
    lang = fields.CharEnumField(max_length=20,enum_type=Lang, default=Lang.en)
    created_at = fields.DatetimeField(auto_now_add=True,use_tz=True)
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
        #'opt_in_code':self.opt_in_code,
        'frequency':self.frequency.value,
        'status':self.status.value,
        'lang': self.lang.value,
        'created_at': self.created_at.isoformat(),
        'update_at':self.updated_at.isoformat(),
    }

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        schema = CONTACTS_SCHEMA
        table = "contact"

class SecurityContactORM(Model):
    security_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
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
        table = "securitycontact"

class SubscriptionContactStatusORM(Model):
    subscription_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    contact = fields.ForeignKeyField('models.ContactORM', related_name='subscriptions_status', unique=True,on_delete=fields.CASCADE, on_update=fields.CASCADE)
    email_status = fields.CharEnumField(enum_type=SubscriptionStatus,max_length=20)
    sms_status = fields.CharEnumField(enum_type=SubscriptionStatus,max_length=20)
    created_at = fields.DatetimeField(auto_now_add=True,use_tz=True)
    updated_at = fields.DatetimeField(auto_now=True,use_tz=True)

    def __str__(self):
        return f"{self.subscription_id} {self.contact}"

    class Meta:
        table = "subscriptioncontact"
        schema = CONTACTS_SCHEMA

class ReasonORM(Model):
    reason_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    reason_description = fields.TextField(null=True)
    reason_name = fields.CharField(max_length=255, unique=True)
    reason_count = fields.BigIntField(default=0)

    class Meta:
        table = "reason"
        schema = CONTACTS_SCHEMA

class ContentSubscriptionORM(Model):
    content_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    content_name = fields.CharField(max_length=50, unique=True)
    content_description = fields.TextField(null=True)
    content_type = fields.CharEnumField(max_length=20,enum_type=ContentType)
    content_ttl = fields.DatetimeField()
    created_at = fields.DatetimeField(auto_now_add=True,use_tz=True)
    updated_at = fields.DatetimeField(auto_now=True,use_tz=True)
    

    class Meta:
        table = "subscontent"
        schema = CONTACTS_SCHEMA

class SubscriptionORM(Model):
    subs_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    contact = fields.ForeignKeyField('models.ContactORM', related_name='subscription', on_delete=fields.CASCADE, on_update=fields.CASCADE)
    content = fields.ForeignKeyField('models.ContentSubscriptionORM', related_name='content', on_delete=fields.CASCADE, on_update=fields.CASCADE)
    subs_status = fields.CharEnumField(max_length=20, enum_type=SubscriptionStatus, default=SubscriptionStatus.Active)
    created_at = fields.DatetimeField(auto_now_add=True, use_tz=True)
    updated_at = fields.DatetimeField(auto_now=True, use_tz=True)
    preferred_method = fields.CharEnumField(enum_type=Relay,max_length=20)

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

class ContactAnalyticsORM(Model):
    analytics_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    content = fields.ForeignKeyField('models.ContentSubscriptionORM','analytics',null=True,on_delete=fields.NO_ACTION,)
    week_start_date = fields.DateField(default=datetime.utcnow().date)
    country = fields.CharField(max_length=5, null=True)
    region = fields.CharField(max_length=60, null=True)
    city = fields.CharField(max_length=100, null=True)
    subscriptions_count = fields.IntField(default=0)
    unsubscriptions_count = fields.IntField(default=0)

    class Meta:
        schema = CONTACTS_SCHEMA
        table = "contactanalytics"
        unique_together = ("week_start_date", "country", "region", "city")

    @property
    def to_json(self):
        return {
            "analytics_id": str(self.analytics_id),
            "content_id":str(self.content.content_id) if self.content != None else None,
            "week_start_date": self.week_start_date.isoformat(),
            "country": self.country,
            "region": self.region,
            "city": self.city,
            "subscriptions_count": self.subscriptions_count,
            "unsubscriptions_count": self.unsubscriptions_count,
        }
    
class ContactCreationAnalyticsORM(Model):
    analytics_id = fields.UUIDField(pk=True, default=uuid_v1_mc)
    week_start_date = fields.DateField(default=datetime.utcnow().date)
    country = fields.CharField(max_length=5, null=True)
    region = fields.CharField(max_length=60, null=True)
    city = fields.CharField(max_length=100, null=True)
    contacts_created_count = fields.IntField(default=0)

    class Meta:
        schema = CONTACTS_SCHEMA
        table = "contactcreationanalytics"
        unique_together = ("week_start_date", "country", "region", "city")

    @property
    def to_json(self):
        return {
            "analytics_id": str(self.analytics_id),
            "week_start_date": self.week_start_date.isoformat(),
            "country": self.country,
            "region": self.region,
            "city": self.city,
            "contacts_created_count": self.contacts_created_count,
        }
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
    app_registered:bool # BUG because in the landing someone set it to true and access Registered user 
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

    @model_validator(mode="after")
    def check_email_phone(self)->Self:
        if self.phone ==None and self.email == None:
            raise ValueError("Email and phone cant be both null")
        return self


class UpdateContactModel(ContactModel):
    first_name:str | None= None
    last_name:str | None = None
    #app_registered:bool| None = None
    lang:str | None = None
    frequency:Frequency | None = None
    

    @model_validator(mode="after")
    def check_email_phone(self)->Self:
        return self

    @model_validator(mode="after")
    def check_value(self)->Self:
        if not all(self.model_dump().values()):
            raise ValueError("Cant update with an empty body")
        return self
        
class AppRegisteredContactModel(BaseModel):
    app_registered:bool

    
class SecurityModel(BaseModel):
    security_code:int
    security_phrase:str

    @field_validator('security_code')
    def  check_security_code(cls,security_code):
        if not (security_code >=100000 and  security_code<=999999):
            raise ValueError("Value is not a valid 6 digit format")
        return security_code

class ContentSubscriptionModel(BaseModel):
    content_name:str = None
    content_description:str = None
    content_type:ContentType = None
    content_ttl: Optional[datetime] = None   

    @model_validator(mode="after")
    def check_content(self)->Self:
        if not self.content_name and not self.content_description and not self.content_type and not self.content_type:
            raise ValueError('All Value cannot be null')
        return self


##################################################################              ##############################################################3333333333

def query(method:Literal['update','reset']): return f'SELECT {method}_reason($1::VARCHAR(50))'

async def delete_subscriptions_by_contact(contact_id):
    client = Tortoise.get_connection('default')
    q = "SELECT delete_subscriptions_by_contact($1::UUID)"
    row_count, _=await client.execute_query(q,[contact_id])
    return row_count

async def reset_reason(name:str):
    q = query('reason')
    client = Tortoise.get_connection('default')
    await client.execute_query(q,[name])
    
async def update_reason(name:str):
    q = query('update')
    client = Tortoise.get_connection('default')
    await client.execute_query(q,[name])

async def get_contact_summary(contact_id: str):
    query = "SELECT * FROM contacts.contactsummary WHERE contact_id = $1::UUID"
    client = Tortoise.get_connection('default')
    result = await client.execute_query(query, [contact_id])
    return dict(result[1][0]) if result else None

async def get_all_contact_summary():
    query = "SELECT * FROM contacts.contactsummary"
    client = Tortoise.get_connection('default')
    return await client.execute_query(query,[])

async def bulk_upsert_contact_analytics(analytics_data:dict):
    values_str = ", ".join(
        f"ROW('{country}', '{region}', '{city}', {data['subscriptions']}, {data['unsubscriptions']})::contacts.analytics_input"
        for (country, region, city), data in analytics_data.items()
    )
    query = "SELECT * FROM contacts.bulk_upsert_contact_analytics($1)"
    client = Tortoise.get_connection('default')
    return await client.execute_query(query, [f"ARRAY[{values_str}]"])

async def calculate_contact_analytics_grouped(group_by_factor: int):
    query = """
        SELECT * FROM contacts.calculate_contact_analytics_grouped($1);
    """
    client = Tortoise.get_connection('default')
    rows = await client.execute_query(query, [group_by_factor])
    return [
        {
            "group_number": row[0],
            "subscriptions_count": row[1],
            "unsubscriptions_count": row[2],
        }
        for row in rows[1]
    ]

async def bulk_upsert_contact_creation_analytics(analytics_data:dict):
    values_str = ", ".join(
        f"ROW('{country}', '{region}', '{city}', {contacts_created})::contacts.creation_analytics_input"
        for (country, region, city), contacts_created in analytics_data.items()
    )
    query = "SELECT * FROM contacts.bulk_upsert_contact_creation_analytics($1)"
    client = Tortoise.get_connection('default')
    return await client.execute_query(query, [f"ARRAY[{values_str}]"])

async def calculate_contact_creation_analytics_grouped(group_by_factor: int):
    query = """
        SELECT * FROM contacts.calculate_contact_creation_analytics_grouped($1);
    """
    client = Tortoise.get_connection('default')
    rows = await client.execute_query(query, [group_by_factor])
    return [
        {
            "group_number": row[0],
            "country": row[1],
            "region": row[2],
            "city": row[3],
            "contacts_created_count": row[4],
        }
        for row in rows[1]
    ]

class ContactSummary(TypedDict):
    contact_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    app_registered: Optional[bool] = None
    lang: Optional[str] = None
    frequency: Optional[str] = None
    created_at: str
    updated_at: str
    has_security_code: bool
    has_security_phrase: bool
    has_voice_embedding: bool
    email_status: str
    sms_status: str
    subscription_count: int
    newsletter_status: Optional[bool] = None
    promotion_status: Optional[bool] = None
    event_status: Optional[bool] = None
    other_status: Optional[bool] = None
    content_type_subs_updated_at: Optional[str] = None
