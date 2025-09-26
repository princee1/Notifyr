from datetime import datetime
from typing import Any, Optional, Type, Union, ClassVar
from typing_extensions import Literal
from pydantic import EmailStr, Field
from beanie import Document

from app.classes.mail_provider import AuthToken, TokenType
from app.classes.profiles import ProfileModelAuthToken, ProfilModelConstant, ProfileState
from app.utils.constant import EmailHostConstant, MongooseDBConstant


# Type aliases
ProfileType = Literal["email", "twilio"]
ServiceMode = Literal["smtp", "aws", "api", "imap"]
SMTPConnMode = Literal["tls", "ssl", "normal"]


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
# Base Profile Model (Abstract)
######################################################
class ProfileModel(Document):
    profile_type: str | Any = Field(default=None)
    alias: str
    description: str
    role: list[str] = Field(default_factory=list)
    profile_state: ProfileState = ProfileState.ACTIVE
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    last_modified: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    version: int = 1

    _secret_key: ClassVar[list[str]] = []

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
# Email-related Profiles
######################################################
class EmailProfileModel(ProfileModel):
    email_address: EmailStr

    class Settings:
        name = MongooseDBConstant.PROFILE_COLLECTION
        indexes = [
            {"key": ("profile_type", "email_address"), "unique": True}
        ]


class ProtocolProfileModel(EmailProfileModel):
    username: Optional[str] = None
    conn_method: SMTPConnMode
    email_host: EmailHostConstant


class APIEmailProfileModel(EmailProfileModel):
    oauth_tokens: ProfileModelAuthToken


######################################################
# Concrete Implementations
######################################################
class SMTPProfileModel(ProtocolProfileModel):
    profile_type: Literal["email:smtp"] = ProfilModelConstant.SMTP
    from_emails: list[str] = Field(default_factory=list)
    password: Optional[str] = None
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None
    oauth_tokens: Optional[ProfileModelAuthToken | Any] = None

    _secret_key: ClassVar[list[str]] = ["password"]


class IMAPProfileModel(ProtocolProfileModel):
    profile_type: Literal["email:imap"] = ProfilModelConstant.IMAP
    password: str
    imap_server: Optional[str] = None
    imap_port: Optional[int] = None

    _secret_key: ClassVar[list[str]] = ["password"]


class AWSProfileModel(EmailProfileModel):
    profile_type: Literal["email:aws"] = ProfilModelConstant.AWS
    region_name: str
    s3_bucket_name: str
    aws_access_key_id: str
    aws_secret_access_key: str

    _secret_key: ClassVar[list[str]] = ["aws_access_key_id", "aws_secret_access_key"]


class GMailAPIProfileModel(APIEmailProfileModel):
    profile_type: Literal["email:gmail-api"] = ProfilModelConstant.GMAIL_API
    oauth_tokens: ProfileModelAuthToken


class OutlookAPIProfileModel(APIEmailProfileModel):
    profile_type: Literal["email:outlook-api"] = ProfilModelConstant.OUTLOOK_API
    client_id: str
    client_secret: str
    tenant_id: str

    _secret_key: ClassVar[list[str]] = ["client_secret"]


######################################################
# Twilio Profile
######################################################
class TwilioProfileModel(ProfileModel):
    profile_type: Literal["twilio"] = "twilio"
    account_sid: str
    auth_token: str
    from_number: str
    twilio_otp_number: str
    twilio_chat_number: str
    twilio_automated_response_number: str

    _secret_key: ClassVar[list[str]] = ["auth_token"]


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
