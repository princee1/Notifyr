from typing import Any, List
from app.definition._utils_decorator import Guard
from app.container import Get, InjectInMethod
from app.models.contacts_model import ContactORM, ContentType, ContentTypeSubscriptionORM, Status, ContentSubscriptionORM, SubscriptionContactStatusORM
from app.services.assets_service import AssetService
from app.services.celery_service import BackgroundTaskService, CeleryService,task_name
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.logger_service import LoggerService
from app.services.security_service import JWTAuthService
from app.services.twilio_service import TwilioService
from app.utils.constant  import HTTPHeaderConstant
from app.classes.celery import TaskHeaviness, TaskType,SchedulerModel
from app.utils.helper import flatten_dict,b64_encode
from fastapi import HTTPException,status

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
    #TODO If a route allowed a certain type asset
    def __init__(self,content_keys=[],allowed_path=[],options=[]):
        super().__init__()
        self.assetService = Get(AssetService)       
        self.configService = Get(ConfigService)
        self.options = options
        self.allowed_path = [self.configService.ASSET_DIR +p for p in  allowed_path]
        self.content_keys = content_keys

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
    #TODO Check before hand if the background task and the workers are available to do some job
    def __init__(self, heaviness:TaskHeaviness=None):
        super().__init__()
        self.celeryService = Get(CeleryService)
        self.bckgroundTaskService = Get(BackgroundTaskService)
        self.heaviness = heaviness
    
    def guard(self,scheduler:SchedulerModel):
        task_heaviness:TaskHeaviness = scheduler.heaviness
        ...


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
