from typing import Literal, TypedDict,Dict,NotRequired

RoutePermissionScope= Literal['custom','all']

class RoutePermission(TypedDict):
    scope: RoutePermissionScope
    custom_routes: NotRequired[list[str]]

class AuthPermission(TypedDict):
    generation_id: str
    #domain_name:str
    #client_id: str
    #app_id: str
    issued_for: str
    created_at: float
    expired_at: float
    allowed_routes: Dict[str, RoutePermission]



