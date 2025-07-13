from abc import ABCMeta, abstractmethod
from fastapi import HTTPException,status
from app.classes.celery import SchedulerModel
from app.models.contacts_model import ContactORM
from app.models.security_model import ChallengeORM, ClientORM
from app.services.admin_service import AdminService
from app.services.assets_service import DIRECTORY_SEPARATOR, REQUEST_DIRECTORY_SEPARATOR, AssetService, RouteAssetType
from app.definition._utils_decorator import Permission
from app.container import InjectInMethod, Get
from app.services.contacts_service import ContactsService
from app.services.security_service import SecurityService,JWTAuthService
from app.classes.auth_permission import AuthPermission, ClientType, ContactPermission, ContactPermissionScope, RefreshPermission, Role, RoutePermission,FuncMetaData, TokensModel
from app.utils.helper import APIFilterInject
from app.utils.helper import flatten_dict

 
class JWTRouteHTTPPermission(Permission):
    
    def __init__(self,accept_inactive=False,accept_expired=False):
        super().__init__()
        self.jwtAuthService:JWTAuthService = Get(JWTAuthService)
        self.accept_inactive = accept_inactive
        self.accept_expired = accept_expired
    
    def permission(self,class_name:str, func_meta:FuncMetaData, authPermission:AuthPermission):
        
        if authPermission == None:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED,detail="Auth Permission not implemented")
        
        if authPermission['status'] == 'inactive' and not self.accept_inactive:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Permission not active")
        
        if authPermission['status'] == 'expired' and not self.accept_expired:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Permission expired")

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

    def __init__(self,template_type:RouteAssetType,model_keys:list[str]=[],options=[]):
        #TODO Look for the scheduler object and the template
        super().__init__()
        self.jwtAuthService:JWTAuthService = Get(JWTAuthService)
        self.assetService:AssetService = Get(AssetService)
        self.model_keys=model_keys
        self.template_type = template_type
        self.options = options

    def permission(self,authPermission:AuthPermission,template:str,scheduler:SchedulerModel=None,template_type:RouteAssetType=None):
        assetPermission = authPermission['allowed_assets']
        template_type = self.template_type if template_type == None else template_type
        permission = tuple(assetPermission)
        if scheduler == None:
            return True
        if template:
            for content in scheduler.model_dump(include={'content'}):
                t = template.replace(REQUEST_DIRECTORY_SEPARATOR,DIRECTORY_SEPARATOR)
                t = self.assetService.asset_rel_path(t,template_type)
                if not t.startswith(permission):
                        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail={'message':f'Assets [{t}] not allowed' })
                
                content = flatten_dict(content)
                if not self.assetService.verify_asset_permission(content,self.model_keys,assetPermission,self.options):
                    return False
                        
        return True


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
    

class JWTRefreshTokenPermission(Permission):

    def __init__(self,accept_inactive=False):
        super().__init__()
        self.accept_inactive = accept_inactive
        self.jwtAuthService:JWTAuthService = Get(JWTAuthService)
    
    async def permission(self,tokens:TokensModel,authPermission:AuthPermission):
        permission:RefreshPermission = self.jwtAuthService.verify_refresh_permission(tokens.tokens)

        client_id = permission['client_id']

        if permission['status'] != 'active' and not self.accept_inactive:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission not active")

        if client_id != authPermission['client_id']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client Error")

        if permission['client_type'] != authPermission['client_type']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client type mismatch")

        if permission['generation_id'] != authPermission['generation_id']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Generation ID mismatch")

        if permission['group_id'] != authPermission['group_id']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Group ID mismatch")

        if permission['issued_for'] != authPermission['issued_for']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client Error")

        challenge = await ChallengeORM.filter(client=client_id).first()
        if challenge.challenge_refresh != permission['challenge']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Challenge not valid")
        
        return True

class ClientTypePermission(Permission):

    def __init__(self,client_type:ClientType,ensure=False):
        super().__init__()
        self.ensure =ensure
        self.client_type = client_type

    async def permission(self,authPermission:AuthPermission):

        client_id = authPermission['client_id']
        if self.ensure:
            client = await ClientORM.get(client=client_id)
            if client.client_type != self.client_type:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Client is not an {self.client_type.value}")

        if not authPermission['client_type'] == self.client_type.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Client type is not {self.client_type.value}")

        return True     
class AdminPermission(ClientTypePermission):
    # only because theres 3 type of client otherwise there would be only the ClientTypePermission class

     def __init__(self, ensure=False):
        super().__init__(ClientType.Admin, ensure)

class TwilioPermission(ClientTypePermission):

    def __init__(self,ensure=False):
        super().__init__(ClientType.Twilio, ensure)

class UserPermission(ClientTypePermission):

    def __init__(self,ensure=False,accept_none_auth=False):
        super().__init__(ClientType.User, ensure)
        self.accept_none_auth = accept_none_auth
    
    async def permission(self, authPermission:None=None):
        if authPermission == None:
            return self.accept_none_auth
        return await super().permission(authPermission)


async def same_client_authPermission(authPermission:AuthPermission, client:ClientORM):
    if not authPermission['client_id'] == str(client.client_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client ID mismatch")
    
    return True


class BalancerPermission(Permission):
    
    def permission(self):
        return True
