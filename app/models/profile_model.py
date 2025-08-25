from enum import Enum
from typing import Optional
from typing_extensions import Literal
from odmantic import Model, Field, Reference
from app.classes.mail_provider import AuthToken, MongooseAuthToken
from app.utils.constant import EmailHostConstant, MongooseDBConstant
from pydantic import EmailStr, constr, PrivateAttr


ProfileType = Literal['email','twilio']
ServiceMode = Literal['smtp','aws','api','imap']
SMTPConnMode = Literal['tls','ssl','normal']

class ProfileState(Enum):
    ...

######################################################                   ####################################################33
class ProfileModel(Model, collection=MongooseDBConstant.PROFILE_COLLECTION):
    profile_type: ProfileType = Field(..., description="The type of profile")
    profile_state: ProfileState

    
######################################################                   ####################################################33


class EmailProfileModel(ProfileModel, collection=MongooseDBConstant.PROFILE_COLLECTION):
    profile_type = Field('email', const=True)
    email_service : Literal['smtp','aws','api'] = Field(..., description="The email service to use")
    email_address: EmailStr = Field(..., description="The email address",unique=True)


class ProtocolProfileModel(ProfileModel, collection= MongooseDBConstant.PROFILE_COLLECTION):
    service_mode:ServiceMode = Field('smtp', const=True)
    username: str = Field(..., description="The SMTP username")
    conn_method: SMTPConnMode = Field(..., description='The SMTP connection method')
    email_host:EmailHostConstant


class SMTPProfileModel(ProtocolProfileModel, collection=MongooseDBConstant.PROFILE_COLLECTION):
    from_emails:list[str] = Field([])
    password: Optional[str] = Field(..., description="The SMTP password")
    smtp_server: str = Field(..., description="The SMTP server address")
    smtp_port: int = Field(..., description="The SMTP server port")
    oauth_tokens: MongooseAuthToken = Field(...,description="The tokens")


class IMAPProfileModel(ProtocolProfileModel,collection=MongooseDBConstant.PROFILE_COLLECTION):
    password: str = Field(..., description="The IMAP password")
    imap_server: str = Field(..., description="The IMAP server address")
    imap_port: int = Field(..., description="The IMAP server port")




######################################################                   ####################################################33
    

class TwilioProfileModel(ProfileModel, collection=MongooseDBConstant.PROFILE_COLLECTION):
    profile_type = Field('twilio', const=True)
    account_sid: str = Field(..., description="The Twilio Account SID")
    auth_token: str = Field(..., description="The Twilio Auth Token")
    from_number: str = Field(..., description="The Twilio From Phone Number")   
    twilio_otp_number: str = Field(..., description="The Twilio OTP Phone Number")
    twilio_chat_number: str = Field(..., description="The Twilio Chat Phone Number")
    twilio_automated_response_number: str = Field(..., description="The Twilio Automated Response Phone Number")