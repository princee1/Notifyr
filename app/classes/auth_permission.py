from dataclasses import dataclass
from typing import Callable, List, Literal,Dict,NotRequired, Optional, Self
from pydantic import BaseModel, field_validator, model_validator
from typing_extensions import TypedDict
from enum import Enum
from time import time
from .template import Extension
from app.definition._error import BaseError
from app.utils.fileIO import is_file
from app.utils.helper import filter_paths, subset_model

PermissionScope= Literal['custom','all']

ContactPermissionScope = Literal['update','create','any']
PermissionStatus= Literal['active','inactive','expired']
ClientTypeLiteral = Literal['User','Admin']

PolicyUpdateMode = Literal['set','merge','delete']

EXTENSION = [f".{ext}" for ext in Extension._value2member_map_.keys()]

class Role(Enum):
    PUBLIC = 'PUBLIC'
    ADMIN = 'ADMIN'
    RELAY = 'RELAY'
    CUSTOM ='CUSTOM'
    MFA_OTP ='MFA_OTP'
    CHAT = 'CHAT'
    REDIS_RESULT = 'REDIS-RESULT'
    REFRESH = 'REFRESH'
    CONTACTS = 'CONTACTS'
    TWILIO = 'TWILIO'
    SUBSCRIPTION = 'SUBSCRIPTION'
    CLIENT = "CLIENT"
    LINK = "LINK"
    ASSETS = "ASSETS"
    PROFILE ="PROFILE"

class Scope(Enum):
    SoloDolo = 'SoloDolo'
    Organization = 'Organization'
    Domain = 'Domain'
    Free='Free'


class ClientType(Enum):
    User = 'User'
    Admin = 'Admin'
    Twilio = 'Twilio'


class AuthType(Enum):
    ACCESS_TOKEN = 'ACCESS_TOKEN'
    API_TOKEN = 'API_TOKEN'


class FuncMetaData(TypedDict):
    operation_id:str
    roles:set[Role]
    excludes:set[Role]
    options: list[Callable]
    shared:bool
    limit_obj:dict
    limit_exempt:bool=False
    default_role:bool =True


class RoutePermission(TypedDict):
    scope: PermissionScope
    custom_routes: NotRequired[list[str]]

class AssetsPermission(TypedDict):
    scope: PermissionScope
    name: str
    custom_files: NotRequired[list[str]]

class AssetsPermission(TypedDict):
    files: list[str] = []
    dirs: set[str] = []
        
class AuthPermission(TypedDict):
    generation_id: str
    client_username: str
    client_id: str
    client_type:ClientTypeLiteral = 'User'
    roles:list[str|Role]
    issued_for: str # Subnets
    group_id:str | None = None
    auth_type:AuthType
    created_at: float
    expired_at: float
    allowed_routes: Dict[str, RoutePermission]
    allowed_assets:List[str] | AssetsPermission
    allowed_profiles:List[str]=[]
    challenge: str
    scope:str
    salt:str
    status:PermissionStatus= 'active'
    authz_id:str

class RefreshPermission(TypedDict): # NOTE if someone from an organization change the auth permission, the refresh token will be invalid for other people in the organization
    generation_id: str
    challenge:str
    salt:str
    client_id:str
    group_id:str | None = None
    issued_for:str
    created_at:float
    expired_at:float
    status:PermissionStatus= 'active'
    client_type:ClientTypeLiteral = 'User'


class RoutePermissionModel(BaseModel):
    scope:PermissionScope
    custom_routes:Optional[List[str]] = []

    @model_validator(mode='after')
    def check_model(self)->Self:
        if self.scope == 'all':
            self.custom_routes = []
        else:
            if not self.custom_routes:
                raise ValueError('Custom Routes must have at least one routes')
        return self


class PolicyModel(BaseModel):
    allowed_profiles:List[str]=[]
    allowed_routes: Dict[str, RoutePermissionModel] = {}
    allowed_assets: List[str] =[]
    roles: Optional[List[Role]] = [Role.PUBLIC]

    @field_validator('allowed_assets')
    def filter_assets_paths(cls,allowed_assets):
        for asset in allowed_assets:
            is_file(asset,allowed_extension=EXTENSION)
        return filter_paths(allowed_assets)
    
    @field_validator('roles')
    def checks_roles(cls, roles: list[Role]):
        if Role.PUBLIC not in roles:
            roles.append(Role.PUBLIC)
        roles = list(set(roles))
        #return roles
        return [r.value for r in roles]

def parse_authPermission_enum(authPermission):
        authPermission["roles"] = [Role._member_map_[r] for r in authPermission["roles"]]
        
def filter_asset_permission(authPermission:AuthPermission):
    files = set()
    dirs = []
    for p in authPermission['allowed_assets']:
        if is_file(p):
            files.add(p)
        else:
            dirs.append(p)
    
    authPermission['allowed_assets'] = AssetsPermission(files=files,dirs=dirs)

class ContactPermission(TypedDict):
    expired_at:int
    contact_id:str
    scope: ContactPermissionScope
    create_at:int
    salt:str

class TokensModel(BaseModel):
    tokens: str

class WSPermission(TypedDict):
    operation_id:str
    run_id:str
    created_at:float
    expired_at:float
    salt:str
    
class WSPathNotFoundError(BaseError):
    ...


def MustHave(role:Role):

    def verify(authPermission:AuthPermission):
        return role in authPermission['roles']

    return verify

def MustNotHave(role:Role):

    def verify(authPermission:AuthPermission):
        return role not in authPermission['roles']

    return verify


def MustHaveRoleSuchAs(*role:Role):

    roles = set(role)
    roles_size= len(roles)
    
    def verify(authPermission:AuthPermission):
        permissionRoles = authPermission['roles']
        return len(roles.intersection(permissionRoles)) == roles_size

    return verify
