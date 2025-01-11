from dataclasses import dataclass
from typing import Literal, TypedDict,Dict,NotRequired

PermissionScope= Literal['custom','all']

class RoutePermission(TypedDict):
    scope: PermissionScope
    custom_routes: NotRequired[list[str]]

@dataclass
class FileRessourcePermission(TypedDict):
    scope: PermissionScope
    name: str
    custom_files: NotRequired[list[str]]

    def __new__(mcls, name, bases, namespace, /, **kwargs):
        return super().__new__(name, bases, namespace, **kwargs)
        
class AuthPermission(TypedDict):
    generation_id: str
    #domain_name:str
    #client_id: str
    #app_id: str
    issued_for: str
    created_at: float
    expired_at: float
    allowed_routes: Dict[str, RoutePermission]
