from typing import List
from app.definition._utils_decorator import Guard
from app.container import Get, InjectInMethod
from app.services.assets_service import AssetService
from app.services.celery_service import BackgroundTaskService, CeleryService,task_name
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.logger_service import LoggerService
from app.services.twilio_service import TwilioService
from app.utils.constant  import HTTPHeaderConstant
from app.classes.celery import TaskHeaviness, TaskType,SchedulerModel
from app.utils.helper import flatten_dict

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
    Guard to check if the callee is in the contact list
    """

    def __init__(self,model_keys:List[str]):
        super().__init__()
        self.contactsService = Get(ContactsService)
        self.model_keys = model_keys


class TwilioLookUpPhoneGuard(Guard):
    def guard(self):
        return super().guard()
