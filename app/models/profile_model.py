import datetime
from enum import Enum
from ssl import SSLSession
from typing import Optional, Type
from typing_extensions import Literal
from odmantic import Model, Field, Reference,sync
from app.classes.mail_provider import AuthToken, TokenType
from app.classes.profile import ProfileModelAuthToken, ProfilModelConstant, ProfileState
from app.definition._error import BaseError
from app.utils.constant import EmailHostConstant, MongooseDBConstant
from pydantic import EmailStr, constr, PrivateAttr
from typing import ClassVar
from pydantic import BaseModel


ProfileType = Literal['email','twilio']
ServiceMode = Literal['smtp','aws','api','imap']
SMTPConnMode = Literal['tls','ssl','normal']


######################################################                   ####################################################33
    
class ErrorProfileModel(Model,collection=MongooseDBConstant.PROFILE_COLLECTION):
    ...

######################################################  Profile Model                 ####################################################33
class ProfileModel(Model, collection=MongooseDBConstant.PROFILE_COLLECTION):
    profile_type: ProfileType = Field(..., description="The type of profile")
    profile_state: ProfileState
    secret_key:ClassVar[list[str]] = []
    created_at: datetime = datetime.utcnow()
    last_modified: datetime = datetime.utcnow()
    version: int = 1


    def __init_subclass__(cls, **kwargs):
        setattr(cls,'_secret_key',cls.secret_key.copy())
        super().__init_subclass__(**kwargs)
    
    @property
    @classmethod
    def secrets_keys(cls):
        return getattr(cls,'_secret_key',[])


@sync(ProfileModel)
async def update_metadata(session: SSLSession, instance: ProfileModel):
    instance.last_modified = datetime.utcnow()
    if instance.id is not None:  # Means it's an update, not a new insert
        instance.version += 1
######################################################                   ####################################################33


class EmailProfileModel(ProfileModel):
    profile_type:str = Field('email', const=True)
    email_address: EmailStr = Field(..., description="The email address")

    class Config:
        collection =MongooseDBConstant.PROFILE_COLLECTION
        indexes = [
            # Compound unique index
            {"key": ("profile_type", "email_address"), "unique": True}
        ]


class ProtocolProfileModel(EmailProfileModel):
    username: str = Field(..., description="The SMTP username")
    conn_method: SMTPConnMode = Field(..., description='The SMTP connection method')
    email_host:EmailHostConstant


class APIEmailProfileModel(EmailProfileModel):
    oauth_tokens: ProfileModelAuthToken = Field(...,description="The tokens")

######################################################                   ####################################################33

class SMTPProfileModel(ProtocolProfileModel):
    profile_type:str = Field(ProfilModelConstant.SMTP, const=True)
    from_emails:list[str] = Field([])
    password: Optional[str] = Field(..., description="The SMTP password")
    smtp_server: str = Field(..., description="The SMTP server address")
    smtp_port: int = Field(..., description="The SMTP server port")
    oauth_tokens: ProfileModelAuthToken = Field(...,description="The tokens")
    secret_key:ClassVar[list[str]] = ['password']

class IMAPProfileModel(ProtocolProfileModel):
    profile_type:str = Field(ProfilModelConstant.IMAP, const=True)
    password: str = Field(..., description="The IMAP password")
    imap_server: str = Field(..., description="The IMAP server address")
    imap_port: int = Field(..., description="The IMAP server port")
    secret_key:ClassVar[list[str]] = ['password']

class AWSProfileModel(EmailProfileModel):
    profile_type:str = Field(ProfilModelConstant.AWS, const=True)
    region_name:str
    s3_bucket_name:str
    aws_access_key_id:str
    aws_secret_access_key:str
    secret_key:ClassVar[list[str]] = ['aws_access_key_id','aws_secret_access_key']

class GMailAPIProfileModel(APIEmailProfileModel):
    profile_type:str = Field(ProfilModelConstant.GMAIL_API, const=True)
    oauth_tokens: ProfileModelAuthToken = Field(...,description="The tokens")

class OutlookAPIProfileModel(APIEmailProfileModel):
    profile_type:str = Field(ProfilModelConstant.OUTLOOK_API, const=True)
    client_id:str
    client_secret:str
    tenant_id:str
    secret_key:ClassVar[list[str]] = ['client_secret']



######################################################                   ####################################################33


ProfilModelValues:dict[str,Type[ProfileModel]] = {
    ProfilModelConstant.OUTLOOK_API:OutlookAPIProfileModel,
    ProfilModelConstant.GMAIL_API:GMailAPIProfileModel,
    ProfilModelConstant.AWS:AWSProfileModel,
    ProfilModelConstant.IMAP:IMAPProfileModel,
    ProfilModelConstant.SMTP:SMTPProfileModel,

}

######################################################                   ####################################################33
    

class TwilioProfileModel(ProfileModel):
    profile_type:str = Field('twilio', const=True)
    account_sid: str = Field(..., description="The Twilio Account SID")
    auth_token: str = Field(..., description="The Twilio Auth Token")
    from_number: str = Field(..., description="The Twilio From Phone Number")   
    twilio_otp_number: str = Field(..., description="The Twilio OTP Phone Number")
    twilio_chat_number: str = Field(..., description="The Twilio Chat Phone Number")
    twilio_automated_response_number: str = Field(..., description="The Twilio Automated Response Phone Number")


ProfilModelValues.update({
    ProfilModelConstant.TWILIO: TwilioProfileModel
})

######################################################                   ####################################################33
