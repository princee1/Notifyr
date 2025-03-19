from dataclasses import dataclass
from typing import Callable, List, Literal,Dict,NotRequired
from pydantic import BaseModel
from typing_extensions import TypedDict
from enum import Enum
from time import time

from app.definition._error import BaseError

PermissionScope= Literal['custom','all']

ContactPermissionScope = Literal['update','create','any']
PermissionStatus= Literal['active','inactive','expired']

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
    SUBSCRIPTION = 'SUBSCRIPTION'
    CLIENT = "CLIENT"

class Scope(Enum):
    SoloDolo = 'SoloDolo'
    Organization = 'Organization'
    #Domain = 'Domain'


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
    #domain_name:str=None # TODO accept sudomains 
    client_id: str
    application_id: str = None # TODO
    roles:list[str]
    issued_for: str # Subnets
    created_at: float
    expired_at: float
    allowed_routes: Dict[str, RoutePermission]
    allowed_assets:List[str]
    challenge: str
    scope:Scope
    salt:str
    status:PermissionStatus= 'active'

class RefreshPermission(TypedDict): # NOTE if someone from an organization change the auth permission, the refresh token will be invalid for other people in the organization
    generation_id: str
    challenge:str
    salt:str
    client_id:str
    scope_id:str
    issued_for:str
    created_at:float
    expired_at:float
    status:PermissionStatus= 'active'


class ContactPermission(TypedDict):
    expired_at:int
    contact_id:str
    scope: ContactPermissionScope
    create_at:int
    salt:str

class TokensModel(BaseModel):
    tokens: str | list[str]

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
        return role.value in authPermission['roles']

    return verify

def MustNotHave(role:Role):

    def verify(authPermission:AuthPermission):
        return role.value not in authPermission['roles']

    return verify


def MustHaveRoleSuchAs(*role:Role):

    roles = set(role)
    roles_size= len(roles)
    
    def verify(authPermission:AuthPermission):
        permissionRoles = authPermission['roles']
        return len(roles.intersection(permissionRoles)) == roles_size

    return verify
