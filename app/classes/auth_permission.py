from dataclasses import dataclass
from typing import Callable, List, Literal,Dict,NotRequired
from pydantic import BaseModel
from typing_extensions import TypedDict
from enum import Enum

from app.definition._error import BaseError

PermissionScope= Literal['custom','all']



class Role(Enum):
    PUBLIC = 'PUBLIC'
    ADMIN = 'ADMIN'
    RELAY = 'RELAY'
    CUSTOM ='CUSTOM'
    MFA_OTP ='MFA_OTP'
    CHAT = 'CHAT'
    REDIS = 'REDIS'
    REFRESH = 'REFRESH'
    CONTACTS = 'CONTACTS'
    TWILIO = 'TWILIO'


class FuncMetaData(TypedDict):
    operation_id:str
    roles:set[Role]
    excludes:set[Role]
    options: list[Callable]
    limit_obj:dict
    limit_exempt:bool=False


class RoutePermission(TypedDict):
    scope: PermissionScope
    custom_routes: NotRequired[list[str]]

class AssetsPermission(TypedDict):
    scope: PermissionScope
    name: str
    custom_files: NotRequired[list[str]]
        
class AuthPermission(TypedDict):
    generation_id: str
    domain_name:str=None # TODO accept sudomains 
    client_id: str= None # TODO
    application_id: str = None # TODO
    roles:list[str]
    issued_for: str # Subnets
    created_at: float
    expired_at: float
    allowed_routes: Dict[str, RoutePermission]
    allowed_assets:List[str]
    challenge: str= None # TODO 
    scope:list[str] = None # TODO

class TokensModel(BaseModel):
    tokens: str | list[str]

class WSPermission(TypedDict):
    operation_id:str
    run_id:str
    created_at:float
    expired_at:float
    
class WSPathNotFoundError(BaseError):
    ...


def MustHave(role:Role):

    def verify(authPermission:AuthPermission):
        return role.value in authPermission

    return verify
