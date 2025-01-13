from fastapi import HTTPException,status
from services.assets_service import AssetService
from definition._utils_decorator import Permission
from container import InjectInMethod
from services.security_service import SecurityService,JWTAuthService
from classes.permission import RoutePermission


 
class JWTAuthPermission(Permission):
    
    @InjectInMethod
    def __init__(self,jwtAuthService: JWTAuthService):
        super().__init__()
        self.jwtAuthService = jwtAuthService
    
    def permission(self, token_:str, client_ip_:str, class_name:str, func_name:str):
        permission_ = self.jwtAuthService.verify_permission(token_, class_name, func_name,client_ip_)
        operation_id = func_name

        if class_name not in permission_["allowed_routes"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Ressource not allowed")

        routePermission: RoutePermission = permission_["allowed_routes"][class_name]
        if routePermission["scope"] == "all":
            return True

        if operation_id not in routePermission['custom_routes']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Route not allowed")

        return True
    

class JWTAssetPermission(Permission):
    
    @InjectInMethod
    def __init__(self,jwtAuthService: JWTAuthService,assetService: AssetService):
        super().__init__()
        self.jwtAuthService = jwtAuthService
        self.assetService = assetService


    def permission(self, token_, client_ip_, class_name, func_name):
        permission_ = self.jwtAuthService.verify_permission(token_, class_name, func_name,client_ip_)
        assetPermission = permission_['asset_permission']