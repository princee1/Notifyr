from fastapi import HTTPException,status
from app.services.assets_service import AssetService
from app.definition._utils_decorator import Permission
from app.container import InjectInMethod
from app.services.security_service import SecurityService,JWTAuthService
from app.classes.auth_permission import AuthPermission, Role, RoutePermission,FuncMetaData

 
class JWTRouteHTTPPermission(Permission):
    
    @InjectInMethod
    def __init__(self,jwtAuthService: JWTAuthService):
        super().__init__()
        self.jwtAuthService = jwtAuthService
    
    def permission(self,class_name:str, func_meta:FuncMetaData, authPermission:AuthPermission):
        operation_id = func_meta["operation_id"]
        roles= func_meta['roles']
        auth_roles = authPermission["roles"]
        roles_excluded =func_meta['excludes']
        
        if len(roles_excluded.intersection(auth_roles)) > 0:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Role not allowed")

        if len(roles.intersection(auth_roles)) > 0:
                return True
               
        if Role.CUSTOM not in auth_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Role not allowed")
                
        # Role.CUSTOM available
        if class_name not in authPermission["allowed_routes"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ressource not allowed")

        routePermission: RoutePermission =authPermission["allowed_routes"][class_name]
        
        if routePermission["scope"] == "all":
            return True

        if operation_id not in routePermission['custom_routes']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Route not allowed")

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

