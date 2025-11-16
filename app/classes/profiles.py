from datetime import datetime
from enum import Enum
from typing import ClassVar, Optional, Type, TypedDict
from beanie import Document
from typing_extensions import Literal
from pydantic import BaseModel, Field
from app.classes.condition import MongoCondition
from app.classes.mail_provider import TokenType
from app.definition._error import BaseError
from app.utils.constant import MongooseDBConstant, StreamConstant


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
    OUTLOOK_API=f'{EMAIL_PROFILE_TYPE}/outlook-api'
    GMAIL_API=f'{EMAIL_PROFILE_TYPE}/gmail-api'
    AWS=f'{EMAIL_PROFILE_TYPE}/aws'
    IMAP=f'{EMAIL_PROFILE_TYPE}/imap'
    SMTP=f'{EMAIL_PROFILE_TYPE}/smtp'
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
    
    def __init__(self,profile,motor_fallback, *args):
        super().__init__(*args)

        self.profile = profile
        self.motor_fallback=motor_fallback
class ProfileNotAllowedToUseError(BaseError):
    ...

class ProfileDoesNotExistsError(BaseError):
    ...

class ProfileNotSpecifiedError(BaseError):
    ...

class ProfileModelRequestBodyError(BaseError):
    
    def __init__(self,*args,message='Profile model body cannot be parsed into JSON'):
        super().__init__(*args)
        self.message = message
    
class ProfileModelAddConditionError(BaseError):
    ...

class ProfileModelConditionWrongMethodError(BaseError):
    ...


class ProfileModelConditionFilterDoesNotExistOnModelError(BaseError):
    ...
####################################                 #####################################333

class ProfileState(Enum):
    CREATED = 0 
    ACTIVE = 1
    BLOCKED = 2
    INACTIVE = 3
    EXPIRED = 4

class ProfileStateProtocol(TypedDict):
    ...

class ProfileErrorProtocol(TypedDict):
    profile_id:str
    error_type:Literal['connect','authenticate','permission','rate_limit','general']
    profile_status: int
    error_code: Optional[int]
    error_name: Optional[str]
    error_description: Optional[str]
    error_level:Optional[Literal['warn','critical','message']]

class ProfileModelException(BaseException):
    topic = StreamConstant.PROFILE_ERROR_STREAM
    def __init__(self,error:ProfileErrorProtocol):
        super().__init__()
        self.error = error

####################################                 #####################################333


######################################################
# Base Profile Model (Abstract)
######################################################



class BaseProfileModel(Document):

    
    alias: str
    description: Optional[str] = Field(default=None,min_length=0,max_length=1000)
    role: list[str] = Field(default_factory=list)
    profile_state: ProfileState = ProfileState.ACTIVE
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    last_modified: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    version: int = 1

    _secret_key: ClassVar[list[str]] = []
    unique_indexes: ClassVar[list[str]] = []
    condition:ClassVar[Optional[MongoCondition]] = None
    _collection:ClassVar[Optional[str]] = None
    _vault:ClassVar[Optional[str]]  = None
    
    def __init_subclass__(cls, **kwargs):
        # Ensure secret keys are inherited but isolated
        setattr(cls, "_secret_key", cls._secret_key.copy())
        super().__init_subclass__(**kwargs)

    @classmethod
    @property
    def secrets_keys(cls):
        return getattr(cls, "_secret_key", [])



######################################################
# Error Model
######################################################
class ErrorProfileModel(Document):
    profile_id: Optional[str]

    error_code: Optional[int]
    error_name: Optional[str]
    error_description: Optional[str]
    error_level:Optional[Literal['warn','critical','message']]
    error_type:Optional[Literal['connect','authenticate','permission','rate_limit','general']]

    ignore:Optional[bool] = False

    class Settings:
        name = MongooseDBConstant.ERROR_PROFILE_COLLECTION

ProfilModelValues: dict[str, Type[BaseProfileModel]] = {}