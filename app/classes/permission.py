from typing import Literal, TypedDict,Dict,NotRequired

RoutePermissionScope= Literal['custom','all']

class RoutePermission(TypedDict):
    scope: RoutePermissionScope
    custom_routes: NotRequired[list[str]]

class PermissionAuth(TypedDict):
    issued_for: str
    created_at: float
    expired_at: float
    allowed_routes: Dict[str, RoutePermission]



