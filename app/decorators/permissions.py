from fastapi import HTTPException,status
from app.services.assets_service import AssetService
from app.definition._utils_decorator import Permission
from app.container import InjectInMethod
from app.services.security_service import SecurityService,JWTAuthService
from app.classes.permission import AuthPermission, RoutePermission

 
class JWTHTTPRoutePermission(Permission):
    
    @InjectInMethod
    def __init__(self,jwtAuthService: JWTAuthService):
        super().__init__()
        self.jwtAuthService = jwtAuthService
    
    def permission(self,class_name:str, func_name:str,authPermission:AuthPermission):
        operation_id = func_name

        if class_name not in authPermission["allowed_routes"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Ressource not allowed")

        routePermission: RoutePermission =authPermission["allowed_routes"][class_name]
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

    def permission(self,template:str, authPermission:AuthPermission):
        #assetPermission = authPermission['asset_permission']
        return True

