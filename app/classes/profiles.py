from datetime import datetime
from enum import Enum
from typing import ClassVar, Optional, Type, TypedDict
from beanie import Document
from typing_extensions import Literal
from pydantic import BaseModel, Field, field_validator
from app.classes.mongo import BaseDocument
from app.classes.mail_provider import TokenType
from app.definition._error import BaseError
from app.utils.constant import MongooseDBConstant, StreamConstant



class ProfileModelAuthToken(BaseModel):
    access_token: str
    refresh_token: str
    token_type: TokenType
    expires_in: float
    acquired_at: float
    scope: Optional[str] 
    mail_provider: str
    
    secret_key:ClassVar[list[str]]= ['access_token','refresh_token']

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


MAX_LEN =600

class BaseProfileModel(BaseDocument):

    role: list[str] = Field(default_factory=list)
    profile_state: ProfileState = ProfileState.ACTIVE

    _secrets_keys: ClassVar[list[str]] = []
    _vault:ClassVar[Optional[str]]  = None
    _queue:ClassVar[str] = ...
    
    @field_validator("*", mode="before")
    def limit_all_strings(cls, v):
        if isinstance(v, str) and len(v) > MAX_LEN:
            raise ValueError(f"String too long (max {MAX_LEN})")
        return v

    @property
    def profile_id(self):
        return str(self.id)
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