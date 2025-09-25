from datetime import datetime
from typing import Any, Optional, Type
from typing_extensions import Literal
from odmantic import Model, Field, Reference
from app.classes.mail_provider import AuthToken, TokenType
from app.classes.profiles import ProfileModelAuthToken, ProfilModelConstant, ProfileState
from app.utils.constant import EmailHostConstant, MongooseDBConstant
from pydantic import EmailStr, constr, PrivateAttr
from typing import ClassVar


ProfileType = Literal['email','twilio']
ServiceMode = Literal['smtp','aws','api','imap']
SMTPConnMode = Literal['tls','ssl','normal']


######################################################                   ####################################################33
    
class ErrorProfileModel(Model):
    profile_id:str
    error_code:int
    error_name:str
    error_description:str

    model_config = {
        "collection": MongooseDBConstant.PROFILE_COLLECTION
    }

######################################################  Profile Model                 ####################################################33
class ProfileModel():
    profile_type: str | Any
    profile_state: ProfileState
    created_at: str = datetime.utcnow().isoformat()
    last_modified: str = datetime.utcnow().isoformat()
    version: int = 1
    _secret_key:ClassVar[list[str]] = []

    model_config = {
        "collection": MongooseDBConstant.PROFILE_COLLECTION,
    }

    def __init_subclass__(cls, **kwargs):
        setattr(cls,'_secret_key',cls._secret_key.copy())
        setattr(cls,'profile_type',None)
        super().__init_subclass__(**kwargs)
    
    @property
    @classmethod
    def secrets_keys(cls):
        return getattr(cls,'_secret_key',[])


# @sync(ProfileModel)
# async def update_metadata(session: SSLSession, instance: ProfileModel):
#     instance.last_modified = datetime.utcnow()
#     if instance.id is not None:  # Means it's an update, not a new insert
#         instance.version += 1
######################################################                   ####################################################33


class EmailProfileModel(ProfileModel):
    profile_type: str | Any
    email_address: EmailStr 

    model_config = {

    "collection": MongooseDBConstant.PROFILE_COLLECTION,
    "indexes": [
        {"key": ("profile_type", "email_address"), "unique": True}
    ]
    }


class ProtocolProfileModel(EmailProfileModel):
    username: str
    conn_method: SMTPConnMode
    email_host:EmailHostConstant


class APIEmailProfileModel(EmailProfileModel):
    oauth_tokens: ProfileModelAuthToken

######################################################                   ####################################################33

class SMTPProfileModel(ProtocolProfileModel,Model):
    profile_type:Literal['email:smtp'] = ProfilModelConstant.SMTP
    from_emails:list[str]
    password: Optional[str]
    smtp_server: str
    smtp_port: int
    oauth_tokens: ProfileModelAuthToken
    secret_key:ClassVar[list[str]] = ['password']

class IMAPProfileModel(ProtocolProfileModel,Model):
    profile_type:Literal['email:imap'] = ProfilModelConstant.IMAP
    password: str
    imap_server: str
    imap_port: int
    _secret_key:ClassVar[list[str]] = ['password']

class AWSProfileModel(EmailProfileModel,Model):
    profile_type:Literal['email:aws'] = ProfilModelConstant.AWS
    region_name:str
    s3_bucket_name:str
    aws_access_key_id:str
    aws_secret_access_key:str
    _secret_key:ClassVar[list[str]] = ['aws_access_key_id','aws_secret_access_key']

class GMailAPIProfileModel(APIEmailProfileModel,Model):
    profile_type:Literal['email:gmail-api'] = ProfilModelConstant.GMAIL_API
    oauth_tokens: ProfileModelAuthToken

class OutlookAPIProfileModel(APIEmailProfileModel,Model):
    profile_type:Literal['email:outlook-api'] = ProfilModelConstant.OUTLOOK_API
    client_id:str
    client_secret:str
    tenant_id:str
    _secret_key:ClassVar[list[str]] = ['client_secret']



######################################################                   ####################################################33


ProfilModelValues:dict[str,Type[ProfileModel]] = {
    ProfilModelConstant.OUTLOOK_API:OutlookAPIProfileModel,
    ProfilModelConstant.GMAIL_API:GMailAPIProfileModel,
    ProfilModelConstant.AWS:AWSProfileModel,
    ProfilModelConstant.IMAP:IMAPProfileModel,
    ProfilModelConstant.SMTP:SMTPProfileModel,

}

######################################################                   ####################################################33
    

class TwilioProfileModel(ProfileModel,Model):
    profile_type:Literal['twilio'] = 'twilio'
    account_sid: str
    auth_token: str
    from_number: str
    twilio_otp_number: str
    twilio_chat_number: str
    twilio_automated_response_number: str

    _secret_key:ClassVar[list[str]] = ["auth_token"]

ProfilModelValues.update({
    ProfilModelConstant.TWILIO: TwilioProfileModel
})

######################################################                   ####################################################33
