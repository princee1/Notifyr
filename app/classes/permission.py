from dataclasses import dataclass
from typing import Literal, TypedDict,Dict,NotRequired

PermissionScope= Literal['custom','all']

class RoutePermission(TypedDict):
    scope: PermissionScope
    custom_routes: NotRequired[list[str]]

@dataclass
class AssetsPermission(TypedDict):
    scope: PermissionScope
    name: str
    custom_files: NotRequired[list[str]]
        
class AuthPermission(TypedDict):
    generation_id: str
    #domain_name:str
    #client_id: str
    #app_id: str
    issued_for: str
    created_at: float
    expired_at: float
    allowed_routes: Dict[str, RoutePermission]
    #allowed_assets:Dict[str,AssetsPermission]
    #allowed_assets:List[str]

