from fastapi import HTTPException,status
from app.classes.celery import SchedulerModel
from app.definition._cost import Cost
from app.models.contacts_model import ContactORM
from app.models.email_model import BaseEmailSchedulerModel
from app.models.security_model import ChallengeORM, ClientORM
from app.services.assets_service import AssetService, RouteAssetType
from app.definition._utils_decorator import Permission
from app.container import InjectInMethod, Get
from app.services.contacts_service import ContactsService
from app.services.cost_service import CostService
from app.services.database_service import RedisService
from app.services.security_service import SecurityService,JWTAuthService
from app.classes.auth_permission import AuthPermission, AuthType, ClientType, ContactPermission, ContactPermissionScope, RefreshPermission, Role, RoutePermission,FuncMetaData, TokensModel, filter_asset_permission
from app.services.task_service import TaskManager
from app.utils.constant import RedisConstant
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
        
        if authPermission['auth_type'] == AuthType.ACCESS_TOKEN:

            if authPermission['status'] == 'inactive' and not self.accept_inactive:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Permission not active")
            
            if authPermission['status'] == 'expired' and not self.accept_expired:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Permission expired")
        
        if authPermission['client_type'] == ClientType.Admin:
            return True

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

    def __init__(self,template_type:RouteAssetType=None,extension:str=None,model_keys:list[str]=[],options=[],accept_none_template:bool=False):
        #TODO Look for the scheduler object and the template
        super().__init__()
        self.jwtAuthService:JWTAuthService = Get(JWTAuthService)
        self.assetService:AssetService = Get(AssetService)
        self.model_keys=model_keys
        self.template_type = template_type
        self.options = options
        self.extension = extension
        self.accept_none= accept_none_template

    def permission(self,authPermission:AuthPermission,template:str,scheduler:SchedulerModel=None,template_type:RouteAssetType=None):
        if authPermission['client_type'] == ClientType.Admin:
            return True
        
        filter_asset_permission(authPermission)
        template_type = self.template_type if template_type == None else template_type

        if template == '':
            if self.accept_none:
                if template_type==None:
                    return '/' in authPermission['allowed_assets']['dirs']
            else:
                return False
       
        if self.extension:
            template +=f".{self.extension}"
        
        self.assetService.verify_asset_permission(template,authPermission,template_type,self.options)

        if scheduler == None:
            return True

        if len(self.model_keys) == 0:
            return True
        
        for content in scheduler.model_dump(include={'content'}):
            content = flatten_dict(content)
            if not self.assetService.verify_content_asset_permission(content,self.model_keys,authPermission,self.options):
                return False
                                
        return True


class JWTSignatureAssetPermission(JWTAssetPermission):

    def __init__(self):
        super().__init__('email')
    
    def permission(self, authPermission:AuthPermission, scheduler:BaseEmailSchedulerModel):
        if  scheduler.signature == None:
            return True
        if scheduler.signature.template == "":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signature template not provided")
        
        return super().permission(authPermission, scheduler.signature, None, None)

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

        if permission['generation_id'] != authPermission['generation_id']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Generation ID mismatch")

        if permission['group_id'] != authPermission['group_id']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Group ID mismatch")

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


class ProfilePermission(Permission):

    async def permission(self,authPermission:AuthPermission,profile:str):

        if profile not in authPermission['allowed_profiles']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Profile Is not allowed to be used'
            )
        
        return True
    


class CostPermission(Permission):
    """
    Do you have positive units?
    Do you comply to the maximum content and To available ?
    """

    @InjectInMethod(True)
    def __init__(self,costService:CostService,redisService:RedisService):
        super().__init__()
        self.costService = costService
        print(redisService,costService.redisService)
        self.redisService = redisService

    async def permission(self, cost: Cost, taskManager: TaskManager, scheduler: SchedulerModel = None):

        current_credits = await self.redisService.retrieve(
            RedisConstant.LIMITER_DB,
            cost.definition.get('__credit_key__'),
            None
        )
        if current_credits is None:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Credit information unavailable")

        if current_credits <= 0:
            if Cost.rules.get('auto_block_on_zero_credit', False):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client blocked due to zero credits")
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient credits")

        api_cost = cost.definition.get('__api_usage_cost__', 0)
        if current_credits < api_cost:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient credits for API usage")

        if scheduler is not None:
            allowed_tasks = cost.definition.get('__allowed_task_option__', [])
            if scheduler.task_type not in allowed_tasks:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Task type '{scheduler.task_type}' not allowed for this pricing plan"
                )

        if taskManager.meta.get('retry', False) and not Cost.rules.get('retry_allowed', False):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Retry not allowed by pricing policy")

        return True