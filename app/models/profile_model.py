from datetime import datetime
from typing import Any, Optional, Self, Type, Union, ClassVar
from pymongo import ASCENDING
from typing_extensions import Literal
from pydantic import EmailStr, Field, field_validator, model_validator, validator
from beanie import Document

from app.classes.mail_provider import AuthToken, TokenType
from app.classes.phone import PhoneModel
from app.classes.profiles import ProfileModelAuthToken, ProfilModelConstant, ProfileState
from app.utils.constant import EmailHostConstant, MongooseDBConstant
from app.utils.validation import port_validator, phone_number_validator
from app.utils.helper import phone_parser


# Type aliases
ProfileType = Literal["email", "twilio"]
ServiceMode = Literal["smtp", "aws", "api", "imap"]
SMTPConnMode = Literal["tls", "ssl", "normal"]

PROFILE_TYPE_KEY = 'profileType'



######################################################
# Error Model
######################################################
class ErrorProfileModel(Document):
    profile_id: str
    error_code: int
    error_name: str
    error_description: str

    class Settings:
        name = MongooseDBConstant.PROFILE_COLLECTION


######################################################
# Base Profile Model (Root)
######################################################
class ProfileModel(Document):
    alias: str
    description: Optional[str] = Field(default=None,min_length=0,max_length=1000)
    role: list[str] = Field(default_factory=list)
    profile_state: ProfileState = ProfileState.ACTIVE
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    last_modified: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    version: int = 1

    _secret_key: ClassVar[list[str]] = []
    unique_indexes: ClassVar[list[str]] = []
    

    class Settings:
        name = MongooseDBConstant.PROFILE_COLLECTION
        is_root = True 

    def __init_subclass__(cls, **kwargs):
        # Ensure secret keys are inherited but isolated
        setattr(cls, "_secret_key", cls._secret_key.copy())
        super().__init_subclass__(**kwargs)

    @classmethod
    @property
    def secrets_keys(cls):
        return getattr(cls, "_secret_key", [])

######################################################
# Email-related Profiles (Abstract)
######################################################

class EmailProfileModel(ProfileModel):
    profileType:str = 'email'
    email_address: EmailStr

    class Settings:
        abstract = True

class ProtocolProfileModel(EmailProfileModel):
    username: Optional[str] = None
    conn_method: SMTPConnMode
    email_host: EmailHostConstant
    server: Optional[str] = None
    port: Optional[int] = None
    unique_indexes: ClassVar[list[str]] = ['email_host','email_address','username']


    @model_validator(mode='after')
    def host_validation(self)->Self:
        if self.email_host == EmailHostConstant.CUSTOM:
            if not self.server:
                raise ValueError('Server must be defined')

            if self.port == None:
                raise ValueError('Port must be defined')

            port_validator(self.port)

        return self
        
    class Settings:
        abstract = True

class APIEmailProfileModel(EmailProfileModel):
    oauth_tokens: ProfileModelAuthToken
    unique_indexes: ClassVar[list[str]] = ['email_address']

    class Settings:
        abstract = True


######################################################
# Email-related Profiles
######################################################

class SMTPProfileModel(ProtocolProfileModel):
    from_emails: list[str] = Field(default_factory=list)
    password: Optional[str]= None
    oauth_tokens: Optional[ProfileModelAuthToken | Any] = None

    _secret_key: ClassVar[list[str]] = ["password","oauth_tokens"]

    @field_validator('password')
    def password_validation(cls,password:str|None):
        if password == None:
            return password
        if not password:
            raise ValueError('Password not specified')
        
        p_len=len(password)
        if p_len > 500:
            raise ValueError('Password is too big')
    
        return password
    

    @model_validator(mode="after")
    def auth_validation(self)->Self:
        if (not self.oauth_tokens or self.oauth_tokens == {}) and self.password == None:
            raise ValueError('No credentials where provided')
        
        return self

class IMAPProfileModel(ProtocolProfileModel):
    password: str = Field(min_length=1,max_length=400)

    _secret_key: ClassVar[list[str]] = ["password"]

class AWSProfileModel(EmailProfileModel):
    region_name: str
    s3_bucket_name: str
    aws_access_key_id: str
    aws_secret_access_key: str

    _secret_key: ClassVar[list[str]] = ["aws_secret_access_key"]
    unique_indexes: ClassVar[list[str]] = ['aws_access_key_id']

class GMailAPIProfileModel(APIEmailProfileModel):
    oauth_tokens: ProfileModelAuthToken

    _secret_key: ClassVar[list[str]] = ["oauth_tokens"]

class OutlookAPIProfileModel(APIEmailProfileModel):
    client_id: str
    client_secret: str
    tenant_id: str 
    _secret_key: ClassVar[list[str]] = ["client_secret"]


######################################################
# Twilio Profile
######################################################
class TwilioProfileModel(ProfileModel):
    account_sid: str
    auth_token: str
    from_number: PhoneModel | str
    twilio_otp_number: Optional[PhoneModel | str] = None
    twilio_chat_number: Optional[PhoneModel | str] = None
    twilio_automated_response_number: Optional[PhoneModel |str] = None

    _secret_key: ClassVar[list[str]] = ["auth_token"]
    unique_indexes: ClassVar[list[str]] = ['account_sid']

    @field_validator('from_number')
    def from_number_validator(cls,from_number:PhoneModel|str)->str:
        
        if isinstance(from_number,str):
            if not phone_number_validator(from_number):
                raise ValueError('Phone number is not valid')
            return from_number
        else:
            #phone_model = PhoneModel.model_validate(from_number)
            return from_number.phone_number
    
    @field_validator('twilio_otp_number', 'twilio_chat_number', 'twilio_automated_response_number')
    def twilio_phone_validator(cls,number:PhoneModel|None|str):
        if number == None:
            return None
        if isinstance(number,str):
            if not phone_number_validator(number):
                raise ValueError('Phone number is not valid')
            return number
        else:    
            #number = PhoneModel.model_validate(number)
            return number.phone_number
        

######################################################
# Registry of Profile Implementations
######################################################

ProfilModelValues: dict[str, Type[ProfileModel]] = {
    ProfilModelConstant.OUTLOOK_API: OutlookAPIProfileModel,
    ProfilModelConstant.GMAIL_API: GMailAPIProfileModel,
    ProfilModelConstant.AWS: AWSProfileModel,
    ProfilModelConstant.IMAP: IMAPProfileModel,
    ProfilModelConstant.SMTP: SMTPProfileModel,
    ProfilModelConstant.TWILIO: TwilioProfileModel,
}
