from typing import Any, List
from app.classes.auth_permission import AuthPermission, PolicyModel, RefreshPermission
from app.classes.cost_definition import CreditNotInPlanError
from app.definition._error import ServerFileError
from app.definition._utils_decorator import Guard
from app.container import Get, InjectInMethod
from app.depends.class_dep import TrackerInterface
from app.manager.task_manager import TaskManager
from app.models.contacts_model import ContactORM, ContentType, ContentTypeSubscriptionORM, Status, ContentSubscriptionORM, SubscriptionContactStatusORM
from app.models.link_model import LinkORM
from app.models.otp_model import OTPModel
from app.models.security_model import ClientORM
from app.services.admin_service import AdminService
from app.services.cost_service import CostService
from app.services.file.file_service import FileService
from app.services.profile_service import ProfileService
from app.services.worker.task_service import TaskService
from app.services.worker.celery_service import CeleryService,task_name
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.classes.celery import CeleryRedisVisibilityTimeoutError, CelerySchedulerOptionError, TaskHeaviness, TaskType,SchedulerModel
from app.services.worker.arq_service import ArqDataTaskService, DataTaskNotFoundError
from app.utils.constant import CostConstant
from app.utils.helper import APIFilterInject, flatten_dict,b64_encode
from fastapi import HTTPException, Request, UploadFile, status
from app.errors.upload_error import (
    MaxFileLimitError,
    FileTooLargeError,
    TotalFilesSizeExceededError,
    DuplicateFileNameError,
    InvalidExtensionError,
)
from app.utils.globals import CAPABILITIES

class CeleryTaskGuard(Guard):
    def __init__(self,task_names:list[str],task_types:list[TaskType]=[]):
        super().__init__()
        self.task_names = [task_name(t) for t in  task_names]
        self.task_types = task_types
    
    def guard(self,scheduler:SchedulerModel):        
        if self.task_names and scheduler.task_name not in self.task_names:
            return False,f'The task: [{scheduler.task_name}] is  not permitted for this route'
        
        if self.task_types and scheduler.task_type not in self.task_types:
            return False,f'The task_type: [{scheduler.task_type}] is not permitted for this route'
        
        return True,''
                
class TaskWorkerGuard(Guard):
    def __init__(self, heaviness:TaskHeaviness=None):
        super().__init__()
        self.celeryService = Get(CeleryService)
        self.taskService = Get(TaskService)
        self.heaviness = heaviness
    
    async def guard(self,scheduler:SchedulerModel):
        task_heaviness:TaskHeaviness = scheduler._heaviness
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
        is_blacklist,_ =await self.adminService.is_blacklisted(client)

        if is_blacklist:
            return False,'Client is blacklisted'
        return True,''

if CAPABILITIES['twilio']:
    from app.services.ntfr.twilio_service import TwilioService
    class CarrierTypeGuard(Guard):

        def __init__(self,accept_landline:bool,accept_voip:bool=False,accept_unknown:bool=False,):
            super().__init__()
            self.twilioService:TwilioService = Get(TwilioService)
            self.accept_voip = accept_voip
            self.accept_unknown = accept_unknown
            self.accept_landline = accept_landline
        
        async def guard(self,otpModel:OTPModel=None,contact:ContactORM=None,scheduler:SchedulerModel=None):
            return True
            if otpModel != None:
                phone_number = [[otpModel.to]]
            elif contact != None:
                phone_number = [[contact.phone]]
            else:

                phone_number = [[to for to in content.to] for content in scheduler.content]
            for _phone_number in phone_number:
                for pn in _phone_number:
                    status_code,data = await self.twilioService.phone_lookup(phone_number,True)
                    if status_code != 200:
                        return False,f'Callee Information not found: {pn}'
                    
                    carrier:dict= data.get('carrier',None)
                    if carrier == None:
                        return False,f'Carrier Information not found: {pn}'

                    carrier_type = carrier.get('type','unknown')
                    if carrier_type ==None:
                        carrier_type = 'unknown'
                        
                    if carrier_type == 'voip' and not self.accept_voip:
                        return False,f'Carrier Type is Voip: {pn}'
                    if carrier_type == 'landline' and not self.accept_landline:
                        return False,f'Carrier Type is Landline: {pn}'
                    if carrier_type == 'unknown' and not self.accept_unknown:
                        return False,f'Carrier Type is Unknown: {pn}'
                    
            return True,''

class AccessLinkGuard(Guard):
    error_file = 'app/static/error-404-page/index.html'

    def __init__(self,return_file:bool):
        super().__init__()
        self.return_file = return_file

    def guard(self,link:LinkORM):
        link_short_id = link.link_short_id

        if link.public:
            return True,""

        if link.archived:
            if not self.return_file:
                return False,f'Link with short_id: {link_short_id} is currently archived'
            else:
                raise ServerFileError(self.error_file,status.HTTP_410_GONE)
    
        if not link.verified:
            if not self.return_file:
                return False, f'Link with short_id: {link_short_id} is not verified'
            else:
                raise ServerFileError(self.error_file,status.HTTP_410_GONE)
            
        return True,""

    @APIFilterInject
    @staticmethod
    def verify_link_guard(link:LinkORM):

        if link.public:
            return False,'Cannot verify public domain'
        if link.archived:
            return False, 'Cannot verify archived domain'
        if link.verified:
            return False, 'Already verified'

        return True,''

class TrackGuard(Guard):
    allowed=set(['now','once'])

    async def guard(self,scheduler:SchedulerModel,tracker:TrackerInterface):
        return True,''
        if not tracker.will_track:
            return True,''
        if scheduler.task_type not in self.allowed:
            return False,'Cannot track task that are not ran once'
        return True,''

class PolicyGuard(Guard):
    
    def guard(self,policyModel:PolicyModel):
        profileService:ProfileService = Get(ProfileService)
        profiles_set=set(policyModel.allowed_profiles).difference(profileService.MiniServiceStore.ids)
        if len(profiles_set) >= 1:
            return False,f'Those profiles does not exists at the moment: {profiles_set}'
    
        return True,''

class GlobalsTemplateGuard(Guard):

    def __init__(self,error_message:str='Access to the template is forbidden at this route'):
        super().__init__()
        self.error_message = error_message

    def guard(self,template:str=None,files: List[UploadFile]=None,destination_template:str=None):
        if template and template == 'globals.json':
            return False,self.error_message
        if files and 'globals.json' in set([file.filename for file in files]):
            return False,self.error_message
        if destination_template and destination_template == 'globals.json':
            return False,self.error_message

        return True,''


class CeleryBrokerGuard(Guard): 

    _not_allowed_redis_eta = {TaskType.DATETIME,TaskType.TIMEDELTA}
     
    
    def __init__(self,allowed_fallback:bool=False):
        super().__init__()
        self.allowed_fallback = allowed_fallback
        self.configService = Get(ConfigService)
        self.max_visibility_time = self.configService.CELERY_VISIBILITY_TIMEOUT *.15
    
    def guard(self,scheduler:SchedulerModel,taskManager:TaskManager):
        if self.configService.BROKER_PROVIDER == 'redis':
            if scheduler.task_type in self._not_allowed_redis_eta:
                if self.allowed_fallback:
                    taskManager.set_algorithm('aps')
                else:
                    raise CeleryRedisVisibilityTimeoutError
            
            if scheduler.task_type == TaskType.NOW:
                countdown = scheduler.task_option.countdown 
                if countdown and countdown >= self.max_visibility_time:
                    raise CelerySchedulerOptionError("countdown is more than 15 % of the visibility timeout")

        return True,''
    

class UploadFilesGuard(Guard):

    def __init__(self, max_files: int = 5, max_files_size: int | None = None, max_size: int | None = None, allowed_extensions: List[str] | None = None):
        """
        :param max_files: maximum number of files allowed
        :param max_files_size: maximum size per file in bytes (None = no per-file limit)
        :param max_size: maximum total size across all files in bytes (None = no total limit)
        :param allowed_extensions: list of allowed lowercase extensions (e.g. ['.png', '.jpg']) or None
        """
        super().__init__()
        self.max_files = max_files
        self.max_files_size = max_files_size
        self.max_size = max_size
        self.allowed_extensions = [e.lower() for e in allowed_extensions] if allowed_extensions else None
        self.fileService = Get(FileService)

    async def guard(self, files: List[UploadFile]):
        """Validate uploaded files.

        Raises specific BaseError subclasses when validation fails so higher-level handlers
        can convert them into proper HTTP responses.
        """
        if not isinstance(files, list):
            raise HTTPException(status_code=400, detail="files must be a list of UploadFile")

        if self.max_files is not None and len(files) > self.max_files:
            raise MaxFileLimitError(f"Maximum number of files exceeded: {len(files)} > {self.max_files}")

        filenames = set()
        total_size = 0

        for f in files:
            filename = f.filename
                  
            if not filename:
                # treat missing name as invalid
                raise DuplicateFileNameError("<missing>")

            # duplicate names
            if filename in filenames:
                raise DuplicateFileNameError(filename)
            filenames.add(filename)

            # extension check
            if self.allowed_extensions is not None:
                lower = filename.lower()
                ext = self.fileService.get_extension(ext)      
                if ext not in self.allowed_extensions:
                    raise InvalidExtensionError(filename, self.allowed_extensions)

            total_size += f.size

            # per-file size limit
            if self.max_files_size is not None and f.size > self.max_files_size:
                raise FileTooLargeError(filename, f.size, self.max_files_size)

        
            if self.max_size is not None and total_size > self.max_size:
                raise TotalFilesSizeExceededError(total_size, self.max_size)

        return True, ""
    
class ArqDataTaskGuard(Guard):

    def __init__(self,data_task_name:str):
        super().__init__()
        self.data_task_name = data_task_name
        self.arqService = Get(ArqDataTaskService)

    async def guard(self):
        if self.data_task_name not in self.arqService.task_registry:
            raise DataTaskNotFoundError(self.data_task_name)
        
        return True,""
        
    
class CreditPlanGuard(Guard):

    @InjectInMethod()
    def __init__(self,costService:CostService):
        super().__init__()
        self.costService = costService

    def guard(self,credit:CostConstant.Credit):
        if credit not in self.costService.plan_credits:
            raise CreditNotInPlanError(credit)
        
        return True,""