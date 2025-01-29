from dataclasses import dataclass
from typing import Literal,Dict,NotRequired
from typing_extensions import TypedDict
from enum import Enum

PermissionScope= Literal['custom','all']



class Role(Enum):
    PUBLIC = 'PUBLIC'
    ADMIN = 'ADMIN'
    RELAY = 'RELAY'
    CUSTOM ='CUSTOM'
    MFA_OTP ='MFA_OTP'
    CHAT = 'CHAT'


class FuncMetaData(TypedDict):
    operation_id:str
    roles:set[Role]


class RoutePermission(TypedDict):
    scope: PermissionScope
    custom_routes: NotRequired[list[str]]

class AssetsPermission(TypedDict):
    scope: PermissionScope
    name: str
    custom_files: NotRequired[list[str]]
        
class AuthPermission(TypedDict):
    generation_id: str
    #domain_name:str
    #client_id: str
    #app_id: str
    roles:list[str]
    issued_for: str
    created_at: float
    expired_at: float
    allowed_routes: Dict[str, RoutePermission]
    #allowed_assets:Dict[str,AssetsPermission]
    #allowed_assets:List[str]


class WSPermission(TypedDict):
    path:str
    created_at:float
    expired_at:float
    