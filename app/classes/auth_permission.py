from typing import Any, Callable, List, Literal,Dict,NotRequired, Optional, Self
from pydantic import BaseModel, Field, PrivateAttr, field_validator, model_validator
from typing_extensions import TypedDict
from enum import Enum

from app.classes.cost_definition import SimpleTaskCostDefinition
from .template import Extension
from app.definition._error import BaseError
from app.utils.fileIO import is_file
from app.utils.helper import filter_paths, generateId, subset_model

PermissionScope= Literal['custom','all']

ContactPermissionScope = Literal['update','create','any']
PermissionStatus= Literal['active','inactive','expired']
ClientTypeLiteral = Literal['User','Admin','Twilio','App','Service']

PolicyUpdateMode = Literal['set','merge','delete']

EXTENSION = [f".{ext}" for ext in Extension._value2member_map_.keys()]

class Role(Enum):
    PUBLIC = 'PUBLIC'
    STATIC = 'STATIC'
    ADMIN = 'ADMIN'
    RELAY = 'RELAY'
    CUSTOM ='CUSTOM'
    MFA_OTP ='MFA_OTP'
    CHAT = 'CHAT'
    EMAIL = 'EMAIL'
    MESSAGE = 'MESSAGE'
    RESULT = 'RESULT'
    REFRESH = 'REFRESH'
    CONTACTS = 'CONTACTS'
    TWILIO = 'TWILIO'
    SUBSCRIPTION = 'SUBSCRIPTION'
    CLIENT = "CLIENT"
    LINK = "LINK"
    ASSETS = "ASSETS"
    PROFILE ="PROFILE"
    MCP = "MCP"
    AGENT = "AGENT"

class Scope(Enum):
    SoloDolo = 'SoloDolo'
    Organization = 'Organization'
    Domain = 'Domain'
    Free='Free'

class ClientType(Enum):
    User = 'User'
    Admin = 'Admin'
    Twilio = 'Twilio'
    App = 'App'
    Service = 'Service'

class AuthType(Enum):
    ACCESS_TOKEN = 'ACCESS_TOKEN'
    API_TOKEN = 'API_TOKEN'

API_TOKEN_CLIENT_TYPE_SET = {ClientType.Twilio,ClientType.App,ClientType.Service}

class FuncMetaData(TypedDict):
    operation_id:str
    roles:set[Role]
    excludes:set[Role]
    options: list[Callable]
    shared:bool
    limit_obj:dict
    limit_exempt:bool=False
    default_role:bool =True
    to_mcp_tool:bool = False
    tags:list[str]
    cost_definition:SimpleTaskCostDefinition
    cost_definition_name:str

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
        
class MCPPermissionDef(TypedDict):
    tags: list[str]|set[str]
    operations: list[str]|set[str]

class ClientAccessInfo(TypedDict):
    generation_id: str
    created_at: float
    expired_at: float
    generation_id: str
    client_id: str
    status:PermissionStatus= 'active'
    auth_type:AuthType # NOTE Computed value
    client_type:ClientType
    salt:str
    authz_id:str

class ClientRefresh(TypedDict): # NOTE if someone from an organization change the auth permission, the refresh token will be invalid for other people in the organization
    generation_id: str
    authz_id:str
    salt:str
    client_id:str
    created_at:float
    expired_at:float
    status:PermissionStatus= 'active'

class AuthPermission(TypedDict):
    allowed_routes: Dict[str, RoutePermission]
    allowed_assets:List[str] | AssetsPermission
    allowed_profiles:List[str]=[]
    allowed_agents:List[str]=[]
    allowed_blogs: List[str] = []
    allowed_mcp: Optional[MCPPermissionDef] = None
    roles:list[str|Role]=[]

class AccessModel(BaseModel):
    auth_type:AuthType
    access:str

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

class MCPPermissionModel(BaseModel):
    tags:List[str] = Field(default_factory=list, description="List of tags that the user is allowed to access",max_length=20)
    operations:List[str] = Field(default_factory=list, description="List of operations that the user is allowed to access",max_length=20)

    @model_validator(mode='after')
    def check_model(self)->Self:
        if not self.tags and not self.operations:
            raise ValueError('MCPPermission must have at least one tag or operation')
        return self

class PolicyModel(BaseModel):
    allowed_profiles:List[str]=Field(default_factory=list)
    allowed_agents:List[str] = Field(default_factory=list)
    allowed_routes: Dict[str, RoutePermissionModel] = Field(default_factory=dict)
    allowed_mcp: Optional[MCPPermissionModel] = None
    allowed_assets: List[str] = Field(default_factory=list)
    allowed_blog: List[str] = Field(default_factory=list)
    roles: Optional[List[Role]] = Field(default_factory=lambda:[Role.PUBLIC])

    _policy_id:str = PrivateAttr(default=None)

    @field_validator('allowed_assets')
    def filter_assets_paths(cls,allowed_assets):
        for asset in allowed_assets:
            is_file(asset,allowed_extension=EXTENSION)
        return filter_paths(allowed_assets,'/')
    
    @field_validator('roles')
    def checks_roles(cls, roles: list[Role]):
        if Role.PUBLIC not in roles:
            roles.append(Role.PUBLIC)
        roles = list(set(roles))
        #return roles
        return [r.value for r in roles]

    def update(self,model:'PolicyModel',mode:PolicyUpdateMode):
        match mode:
            case 'merge':    
                self.allowed_assets = list(set(model.allowed_assets + self.allowed_assets))
                self.allowed_profiles = list(set(model.allowed_profiles +self.allowed_profiles))
                self.allowed_agents = list(set(model.allowed_agents +self.allowed_agents))
                self.allowed_blog = list(set(model.allowed_blog +self.allowed_blog))
                self.roles = list(set(model.roles + self.roles))
                self.allowed_routes = {**self.allowed_routes,**model.allowed_routes}
            
            case 'set':
                self.allowed_assets = model.allowed_assets
                self.allowed_profiles = model.allowed_profiles
                self.roles = model.roles
                self.allowed_routes = model.allowed_routes
                self.allowed_blog = model.allowed_blog
                self.allowed_agents = model.allowed_agents
            
            case 'delete':
                self.allowed_assets = list(set(self.allowed_assets) - set(model.allowed_assets))
                self.allowed_profiles = list(set(self.allowed_profiles) - set(model.allowed_profiles))
                self.roles = list(set(self.roles) - set(model.roles))
                self.allowed_blog = list(set(self.allowed_blog)-set(model.allowed_blog))
                self.allowed_agents = list(set(self.allowed_agents) - set(model.allowed_agents))
                self.allowed_routes = {k: v for k, v in self.allowed_routes.items() if k not in model.allowed_routes}

def get_combined_policies(policies:list[PolicyModel]):
    roles= set()
    allowed_assets = set()
    allowed_profiles = set()
    allowed_blogs = set()
    allowed_routes = {}
    allowed_agents = set()

    for p in policies:
        roles.update(p.roles)
        allowed_assets.update(p.allowed_assets)
        allowed_profiles.update(p.allowed_profiles)
        allowed_agents.update(p.allowed_agents)
        allowed_blogs.update(p.allowed_blog)

        for k,r in p.allowed_routes.items():

            if k not in allowed_routes:
                allowed_routes[k] = r
            else:
                if r['scope'] == 'all':
                    if allowed_routes['scope'] !='all':
                        allowed_routes['scope'] = 'all'
                        allowed_routes['custom_routes'] = []
                else:
                    if allowed_routes['scope'] == 'custom':
                        allowed_routes['custom_routes'] = list[set(allowed_routes['custom_routes']).union(r['scope'])]

    print(allowed_assets)

    allowed_assets = filter_paths(list(allowed_assets),'/')
    allowed_profiles = list(allowed_profiles)
    allowed_agents = list(allowed_agents)
    roles = list(roles)
    allowed_blogs=list(allowed_blogs)

    return AuthPermission(
        roles=roles,
        allowed_routes=allowed_routes,
        allowed_profiles=allowed_profiles,
        allowed_assets=allowed_assets,
        allowed_agents=allowed_agents,
        allowed_blogs=allowed_blogs
    )

def parse_authPermission_enum(authPermission:AuthPermission):
    authPermission["roles"] = [Role._member_map_[r] for r in authPermission["roles"]]
        
def filter_asset_permission(authPermission:AuthPermission):
    files = set()
    dirs = set()
    for p in authPermission['allowed_assets']:
        if is_file(p):
            files.add(p)
        else:
            dirs.add(p)
    
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

class PoliciesNotMatchingError(BaseError):
    ...

    def __init__(self,policies:list[str]):
        super().__init__(policies)
        self.policies= policies

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

def MustHaveWhen(role:Role,condition:Callable[[AuthPermission,FuncMetaData],bool]=None,configuration:Callable[[],bool]=None):

    def verify(authPermission:AuthPermission=None,func_meta:FuncMetaData=None):
        if configuration and not configuration():
            return True

        if condition is not None:
            if not condition(func_meta):
                return False
            
        return role in authPermission['roles']
        

    verify.need_metadata = True
    return verify


def BypassRole(role:Role):

    def verify(authPermission:AuthPermission):
        return role in authPermission['roles']

    verify.bypass = True

    return verify
