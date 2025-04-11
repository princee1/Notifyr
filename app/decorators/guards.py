from typing import Any, List
from app.classes.auth_permission import AuthPermission, RefreshPermission
from app.definition._utils_decorator import Guard
from app.container import Get, InjectInMethod
from app.models.contacts_model import ContactORM, ContentType, ContentTypeSubscriptionORM, Status, ContentSubscriptionORM, SubscriptionContactStatusORM
from app.models.otp_model import OTPModel
from app.models.security_model import ClientORM
from app.services.admin_service import AdminService
from app.services.assets_service import AssetService
from app.services.celery_service import TaskService, CeleryService,task_name
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.logger_service import LoggerService
from app.services.security_service import JWTAuthService
from app.services.twilio_service import TwilioService
from app.utils.constant  import HTTPHeaderConstant
from app.classes.celery import TaskHeaviness, TaskType,SchedulerModel
from app.utils.helper import flatten_dict,b64_encode
from fastapi import HTTPException, Request,status

class CeleryTaskGuard(Guard):
    def __init__(self,task_names:list[str],task_types:list[TaskType]=None):
        super().__init__()
        self.task_names = [task_name(t) for t in  task_names]
        self.task_types = task_types
    
    def guard(self,scheduler:SchedulerModel):        
        if self.task_names and scheduler.task_name not in self.task_names:
            return False,f'The task: [{scheduler.task_name}] is  not permitted for this route'
        
        if self.task_types != None and scheduler.task_name not in self.task_types:
            return False,f'The task_type: [{scheduler.task_type}] is not permitted for this route'
        
        return True,''

class AssetGuard(Guard):
    
    def __init__(self,content_keys=[],allowed_path=[],options=[],accepted_type=None):
        super().__init__()
        self.assetService = Get(AssetService)       
        self.configService = Get(ConfigService)
        self.options = options
        self.allowed_path = [self.configService.ASSET_DIR +p for p in  allowed_path]
        self.content_keys = content_keys
        self.accepted_type = accepted_type

    def _filter_allowed(self):
        if self.accepted_type != None:
            ...
            #TODO If a route allowed a certain type asset
    def guard(self,scheduler:SchedulerModel):
        if scheduler == None:
            return True,_
        content = scheduler.model_dump(include={'content'})
        content = flatten_dict(content)
        flag = self.assetService.verify_asset_permission(content,self.content_keys,self.allowed_path,self.options)
        if not flag:
            return False, 'message'
        return True,''
                
class TaskWorkerGuard(Guard):
    def __init__(self, heaviness:TaskHeaviness=None):
        super().__init__()
        self.celeryService = Get(CeleryService)
        self.taskService = Get(TaskService)
        self.heaviness = heaviness
    
    async def guard(self,scheduler:SchedulerModel):
        task_heaviness:TaskHeaviness = scheduler.heaviness
        ...
    #TODO Check before hand if the background task and the workers are available to do some job
    # NOTE Already have a pingService



class RegisteredContactsGuard(Guard):
    """
    Guard to check if the callee is registered
    """

    def __init__(self):
        super().__init__()
        self.contactsService:ContactsService = Get(ContactsService)

    def guard(self,contact:ContactORM):
        if contact.app_registered:
            return True,''
        return False,'Contact Must be registered to proceed with this actions'
    
class ActiveContactGuard(Guard):

    async def guard(self,contact:ContactORM,subs_content:ContentSubscriptionORM=None,relay:str=None):

        subs_content_type = subs_content.content_type
        if subs_content:
            if subs_content_type in [ContentType.notification,ContentType.update]:
                return True,''

        if contact.status != Status.Active:
            return False,'Contact is not active yet for non alert content type'
        
        if relay:
            subscription = await SubscriptionContactStatusORM.filter(contact=contact).first()
            relay+='_status'
            if getattr(subscription,relay) != 'Active':
                return False,'Contact method is not active'
            
        if subs_content:
            contact_content_type = await ContentTypeSubscriptionORM.filter(contact=contact).first()

            if not getattr(contact_content_type,subs_content_type):
                return False,'Content Type is not allowed for this user'

        return True,''

class ContactActionCodeGuard(Guard):

    def __init__(self,bypass_content=False):
        super().__init__()
        self.bypass = bypass_content

    def guard(self,action_code:str,contact:ContactORM,subsContent:ContentSubscriptionORM=None):

        if self.bypass:
            if  subsContent.content_type  in [ContentType.notification, ContentType.update]:
                return True,''
                # raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contact status is not active and content type is not permitted")

        if not action_code:
            raise HTTPException(status_code=400, detail="Action code is required")
        
        if not contact.action_code:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contact action code is null at the moment")

        action_code = b64_encode(action_code)
        if action_code != contact.action_code:
            return False,'Contact action Code is not valid'
        
        return True,''

class TwilioLookUpPhoneGuard(Guard):
    def guard(self):
        return super().guard()


class AuthenticatedClientGuard(Guard):
    def __init__(self,reverse=False):
        super().__init__()
        self.reverse = reverse
       
    def guard(self,client:ClientORM):
        if self.reverse:
            if client.authenticated:
                return False,'Client is authenticated'
            return True,''
        
        if not client.authenticated:
            return False,'Client is not authenticated'
        return True,''


class BlacklistClientGuard(Guard):
    def __init__(self):
        super().__init__()
        self.adminService = Get(AdminService)
    
    async def guard(self,client:ClientORM):
        if await self.adminService.is_blacklisted(client):
            return False,'Client is blacklisted'
        return True,''
    

class CarrierTypeGuard(Guard):

    def __init__(self,accept_landline:bool,accept_voip:bool=False,accept_unknown:bool=False,):
        super().__init__()
        self.twilioService:TwilioService = Get(TwilioService)
        self.accept_voip = accept_voip
        self.accept_unknown = accept_unknown
        self.accept_landline = accept_landline
    
    async def guard(self,otpModel:OTPModel=None,contact:ContactORM=None,scheduler:SchedulerModel=None):
        if otpModel != None:
            phone_number = otpModel.to
        elif contact != None:
            phone_number = contact.phone
        else:
            phone_number = scheduler.content.to

        status_code,data = await self.twilioService.phone_lookup(phone_number,True)
        if status_code != 200:
            return False,'Callee Information not found'
        
        carrier= data.get('carrier',None)
        if carrier == None:
            return False,'Carrier Information not found'

        carrier_type = carrier.get('type','unknown')

        if carrier_type == 'voip' and not self.accept_voip:
            return False,'Carrier Type is Voip'
        if carrier_type == 'landline' and not self.accept_landline:
            return False,'Carrier Type is Landline'
        if carrier_type == 'unknown' and not self.accept_unknown:
            return False,'Carrier Type is Unknown'
        return True,''