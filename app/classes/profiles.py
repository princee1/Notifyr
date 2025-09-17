from enum import Enum
from typing import ClassVar, Optional, TypedDict
from pydantic import BaseModel
from app.classes.mail_provider import TokenType
from app.definition._error import BaseError


EMAIL_PROFILE_TYPE = 'email'

class ProfileModelAuthToken(BaseModel):
    access_token: str
    refresh_token: str
    token_type: TokenType
    expires_in: float
    acquired_at: float
    scope: Optional[str] 
    mail_provider: str
    
    secret_key:ClassVar[list[str]]= ['access_token','refresh_token']

class ProfilModelConstant:
    OUTLOOK_API=f'{EMAIL_PROFILE_TYPE}:outlook-api'
    GMAIL_API=f'{EMAIL_PROFILE_TYPE}:gmail-api'
    AWS=f'{EMAIL_PROFILE_TYPE}:aws'
    IMAP=f'{EMAIL_PROFILE_TYPE}:imap'
    SMTP=f'{EMAIL_PROFILE_TYPE}:smtp'
    TWILIO='twilio'

####################################                 #####################################333

class ProfileModelTypeDoesNotExistsError(BaseError):
    
    def __init__(self, e, *args):
        super().__init__(*args)
        self.error = e

class ProfileNotAvailableError(BaseError):
    ...

class ProfileHasNotCapabilitiesError(BaseError):
    ...

class ProfileTypeNotMatchRequest(BaseError):
    ...

class ProfileNotAllowedToUseError(BaseError):
    ...

class ProfileDoesNotExistsError(BaseError):
    ...

####################################                 #####################################333

class ProfileState(Enum):
    ...

class ProfileStateProtocol(TypedDict):
    ...

####################################                 #####################################333

class Profil:

    def __init__(self):
        ...