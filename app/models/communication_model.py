from typing import Any, Optional, Self, Type, TypeVar, Union, ClassVar
from typing_extensions import Literal
from pydantic import ConfigDict, EmailStr, Field, field_validator, model_validator
from app.classes.mongo import MongoCondition
from app.classes.mail_provider import AuthToken, TokenType
from app.classes.phone import PhoneModel
from app.classes.profiles import ProfilModelValues, BaseProfileModel, ProfileModelAuthToken, ProfileState
from app.utils.constant import EmailHostConstant, MongooseDBConstant, VaultConstant
from app.utils.validation import email_validator, port_validator, phone_number_validator,url_validator
from app.utils.helper import phone_parser


# Type aliases
ProfileType = Literal["email", "twilio"]
ServiceMode = Literal["smtp", "aws", "api", "imap"]
ProtocolConnMode = Literal["tls", "ssl", "normal"]

######################################################
# Communication-related Profiles (Root)
######################################################
class CommunicationProfileModel(BaseProfileModel):

    _collection:ClassVar[Optional[str]] = MongooseDBConstant.COMMUNICATION_PROFILE_COLLECTION
    _vault:ClassVar[str] = VaultConstant.COMMUNICATION_SECRETS
    
    class Settings:
        is_root=True
        name=MongooseDBConstant.COMMUNICATION_PROFILE_COLLECTION


######################################################
# Email-related Profiles (Abstract)
######################################################

class EmailProfileModel(CommunicationProfileModel):
    email_address: EmailStr
    _queue:ClassVar[str] = 'email'

    class Settings:
        is_root=True
        collection=MongooseDBConstant.COMMUNICATION_PROFILE_COLLECTION


class ProtocolProfileModel(EmailProfileModel):
    username: Optional[str] = None
    conn_method: ProtocolConnMode
    email_host: EmailHostConstant
    server: Optional[str] = None
    port: Optional[int] = None
    unique_indexes: ClassVar[list[str]] = ['email_host','email_address']


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
        is_root=True
        collection=MongooseDBConstant.COMMUNICATION_PROFILE_COLLECTION

class APIEmailProfileModel(EmailProfileModel):
    oauth_tokens: ProfileModelAuthToken
    unique_indexes: ClassVar[list[str]] = ['email_address']

    class Settings:
        is_root=True
        name=MongooseDBConstant.COMMUNICATION_PROFILE_COLLECTION


######################################################
# Email-related Profiles
######################################################

class SMTPProfileModel(ProtocolProfileModel):
    from_emails: list[str] = Field(default_factory=list)
    password: Optional[str]= None
    oauth_tokens: Optional[ProfileModelAuthToken | Any] = None
    disposition_notification_to: Optional[str] = None
    return_receipt_to: Optional[str] = None
    auth_mode:Literal['password','oauth'] = 'password'
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

    @model_validator(mode='after')
    def email_rd_validation(self,):
        def parse_email(email:str):
            if email == None:
                return None
            if email.lower().strip() == '_same_as_email_address_':
                return self.email_address
            if not email_validator(email):
                raise ValueError('Email format not valid')
            return email
        
        self.disposition_notification_to = parse_email(self.disposition_notification_to)
        self.return_receipt_to = parse_email(self.return_receipt_to)
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
    unique_indexes:ClassVar[list[str]] = ['client_id','tenant_id','email_address']


######################################################
# Twilio Profile
######################################################
class TwilioProfileModel(CommunicationProfileModel):
    account_sid: str
    auth_token: str
    from_number: PhoneModel | str
    twilio_url : str
    twilio_otp_number: Optional[PhoneModel | str] = None
    twilio_chat_number: Optional[PhoneModel | str] = None
    twilio_automated_response_number: Optional[PhoneModel |str] = None
    main:bool = False

    _secret_key: ClassVar[list[str]] = ["auth_token"]
    _queue:ClassVar[str] = 'twilio'

    unique_indexes: ClassVar[list[str]] = ['account_sid']
    condition:ClassVar[Optional[MongoCondition]] = MongoCondition(
        force=True,
        rule={"$ge":1},
        filter={"main":True},
        method='simple-number-validation',
    )

    @field_validator('twilio_url')
    def twilio_url_validator(cls,twilio_url)->str:
        if not url_validator(twilio_url):
            raise ValueError('Url is not valid')
        
        return twilio_url

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
EMAIL_PROFILE_TYPE = 'email'
COMM_PREFIX="communication"

class CommunicationModelConstant:
    OUTLOOK_API=f'{COMM_PREFIX}/{EMAIL_PROFILE_TYPE}/outlook-api'
    GMAIL_API=f'{COMM_PREFIX}/{EMAIL_PROFILE_TYPE}/gmail-api'
    AWS=f'{COMM_PREFIX}/{EMAIL_PROFILE_TYPE}/aws'
    IMAP=f'{COMM_PREFIX}/{EMAIL_PROFILE_TYPE}/imap'
    SMTP=f'{COMM_PREFIX}/{EMAIL_PROFILE_TYPE}/smtp'
    TWILIO=f'{COMM_PREFIX}/twilio'


ProfilModelValues.update({
    CommunicationModelConstant.OUTLOOK_API: OutlookAPIProfileModel,
    CommunicationModelConstant.GMAIL_API: GMailAPIProfileModel,
    CommunicationModelConstant.AWS: AWSProfileModel,
    CommunicationModelConstant.IMAP: IMAPProfileModel,
    CommunicationModelConstant.SMTP: SMTPProfileModel,
    CommunicationModelConstant.TWILIO: TwilioProfileModel,
})

