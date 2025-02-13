from fastapi import HTTPException,status
from app.classes.celery import SchedulerModel
from app.services.assets_service import DIRECTORY_SEPARATOR, REQUEST_DIRECTORY_SEPARATOR, AssetService, RouteAssetType
from app.definition._utils_decorator import Permission
from app.container import InjectInMethod, Get
from app.services.security_service import SecurityService,JWTAuthService
from app.classes.auth_permission import AuthPermission, Role, RoutePermission,FuncMetaData
from app.utils.helper import flatten_dict

 
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

        for options in func_meta['options']:
            if not options(authPermission):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Role details not allowed")
                    
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

    def __init__(self,template_type:RouteAssetType,model_keys:list[str]=[]):
        #TODO Look for the scheduler object and the template
        super().__init__()
        self.jwtAuthService:JWTAuthService = Get(JWTAuthService)
        self.assetService:AssetService = Get(AssetService)
        self.model_keys=model_keys
        self.template_type = template_type

    def permission(self,template:str, scheduler:SchedulerModel, authPermission:AuthPermission):
        assetPermission = authPermission['allowed_assets']
        assetPermission = tuple(assetPermission)
        if template:
            content = scheduler.model_dump(include={'content'})
            template = template.replace(REQUEST_DIRECTORY_SEPARATOR,DIRECTORY_SEPARATOR)
            template = self.assetService.asset_rel_path(template,self.template_type)
            if not template.startswith(assetPermission):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail={'message':f'Assets [{template}] not allowed' })

        content = flatten_dict(content)
        for keys in self.model_keys:
            s_content=content[keys]
            if type(s_content) == list:
                for c in s_content:
                    if type(c) == str:
                        if not c.startswith(assetPermission):
                            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail={'message':f'Assets [{c}] not allowed' })
                    
            elif type(s_content)==str:
                if not c.startswith(assetPermission):
                            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail={'message':f'Assets [{s_content}] not allowed' })      
            else:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail={'message':'Entity not properly accessed'})

        return True

