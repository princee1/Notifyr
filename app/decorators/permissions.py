from fastapi import HTTPException,status
from app.classes.celery import SchedulerModel
from app.models.contacts_model import ContactORM
from app.models.security_model import ClientORM
from app.services.assets_service import DIRECTORY_SEPARATOR, REQUEST_DIRECTORY_SEPARATOR, AssetService, RouteAssetType
from app.definition._utils_decorator import Permission
from app.container import InjectInMethod, Get
from app.services.contacts_service import ContactsService
from app.services.security_service import SecurityService,JWTAuthService
from app.classes.auth_permission import AuthPermission, ContactPermission, ContactPermissionScope, Role, RoutePermission,FuncMetaData
from app.utils.helper import flatten_dict

 
class JWTRouteHTTPPermission(Permission):
    
    def __init__(self,accept_inactive=False):
        super().__init__()
        self.jwtAuthService:JWTAuthService = Get(JWTAuthService)
        self.accept_inactive = accept_inactive
    
    def permission(self,class_name:str, func_meta:FuncMetaData, authPermission:AuthPermission):
        
        if authPermission == None:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED,detail="Auth Permission not implemented")
        
        if authPermission['status'] == 'inactive' and not self.accept_inactive:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Permission not active")

        operation_id = func_meta["operation_id"]
        roles= func_meta['roles']
        auth_roles = authPermission["roles"]
        roles_excluded =func_meta['excludes']

        if options:
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

    def __init__(self,template_type:RouteAssetType,model_keys:list[str]=[],options=[]):
        #TODO Look for the scheduler object and the template
        super().__init__()
        self.jwtAuthService:JWTAuthService = Get(JWTAuthService)
        self.assetService:AssetService = Get(AssetService)
        self.model_keys=model_keys
        self.template_type = template_type
        self.options = options

    def permission(self,template:str, scheduler:SchedulerModel, authPermission:AuthPermission,template_type:RouteAssetType=None):
        assetPermission = authPermission['allowed_assets']
        template_type = self.template_type if template_type == None else template_type
        permission = tuple(assetPermission)
        if template:
            content = scheduler.model_dump(include={'content'})
            template = template.replace(REQUEST_DIRECTORY_SEPARATOR,DIRECTORY_SEPARATOR)
            template = self.assetService.asset_rel_path(template,template_type)
            if not template.startswith(permission):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail={'message':f'Assets [{template}] not allowed' })
            
        if scheduler == None:
            return True
        
        content = flatten_dict(content)
        return self.assetService.verify_asset_permission(content,self.model_keys,assetPermission,self.options)


class JWTQueryAssetPermission(JWTAssetPermission):
     
    def __init__(self,allowed_assets:RouteAssetType, model_keys = [], options=[]):
        """
        Use kwargs the model_keys and options parameter
        """
        super().__init__(None, model_keys, options)
        self.allowed_assets = allowed_assets
        self.template_type=...
        
    def permission(self,template:str, scheduler:SchedulerModel, asset:str,authPermission:AuthPermission):
        self.assetService.check_asset(asset,self.allowed_assets)
        return super().permission(template,scheduler,authPermission,asset)
    

class JWTContactPermission(Permission):

    
    def __init__(self,scope:ContactPermissionScope):
        super().__init__()
        self.contactsService= Get(ContactsService)
        self.jwtAuthSErvice = Get(JWTAuthService)
        self.scope = scope


    def permission(self,contact:ContactORM,contactPermission:ContactPermission,token:str):

        if contact.auth_token != token:
            raise HTTPException(status=403,detail="Token not issued for this user")
        
        if contact.contact_id != contactPermission['contact_id']:
            raise HTTPException(status=403,detail="Token not issued for this user") # NOTE seems non-necessary but fuck it 

        if self.scope =='any':
            return True

        if self.scope != contactPermission['scope']:
            raise HTTPException(status=403,detail="")
        
        return True


class AdminPermission(Permission):

    def permission(self,authPermission:AuthPermission):
        if not authPermission['client_type'] == 'Admin':
            raise ...

        return True        

class TwilioPermission(Permission):

    def permission(self,authPermission:AuthPermission):
        if not authPermission['client_type'] == 'Twilio':
            raise ...

        return True  