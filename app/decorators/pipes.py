from typing import Any, Callable, Coroutine, Literal

from fastapi import HTTPException, Request, Response,status
from fastapi.responses import JSONResponse
from app.classes.auth_permission import AuthPermission, TokensModel
from app.classes.celery import SchedulerModel,CelerySchedulerOptionError,SCHEDULER_VALID_KEYS, TaskType
from app.classes.email import EmailInvalidFormatError
from app.classes.template import TemplateNotFoundError
from app.container import Get, InjectInMethod
from app.depends.class_dep import KeepAliveQuery
from app.models.contacts_model import Status
from app.models.otp_model import OTPModel
from app.models.security_model import ClientORM, GroupClientORM
from app.models.sms_model import OnGoingSMSModel
from app.services.assets_service import AssetService, RouteAssetType, DIRECTORY_SEPARATOR, REQUEST_DIRECTORY_SEPARATOR
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.security_service import JWTAuthService
from app.definition._utils_decorator import Pipe
from app.services.celery_service import CeleryService, TaskManager, task_name
from app.services.twilio_service import TwilioService
from app.utils.helper import AsyncAPIFilterInject, copy_response
from app.utils.validation import email_validator, phone_number_validator
from app.utils.helper import APIFilterInject
from app.depends.variables import parse_to_phone_format
from app.depends.orm_cache import ContactSummaryORMCache
from app.models.contacts_model import ContactSummary

@APIFilterInject
async def _to_otp_path(template:str):
    template = "otp\\"+template
    return {'template':template}

class AuthPermissionPipe(Pipe):

    @InjectInMethod
    def __init__(self,jwtAuthService:JWTAuthService):
        super().__init__(True)
        self.jwtAuthService = jwtAuthService

    def pipe(self,tokens:TokensModel):
        tokens = tokens.model_dump(include={'tokens'})
        if isinstance(tokens,str):
            tokens = [tokens]
        temp = {}
        for token in tokens:
            val = self.jwtAuthService.decode_token(token)
            permission:AuthPermission = AuthPermission(**val)
            temp[permission.issued_for] = permission

        return {'tokens':temp}

class TemplateParamsPipe(Pipe):
    
    def __init__(self,template_type:RouteAssetType,extension:str=None,accept_none=False):
        super().__init__(True)
        self.assetService= Get(AssetService)
        self.configService = Get(ConfigService)
        self.template_type = template_type
        self.extension = extension
        self.accept_none = accept_none
    
    def pipe(self,template:str):
        if template == '' and self.accept_none:
            return {'template':template}
        
        template+="."+self.extension
        asset_routes = self.assetService.exportRouteName(self.template_type)
        template = template.replace(REQUEST_DIRECTORY_SEPARATOR,DIRECTORY_SEPARATOR)
        template = self.assetService.asset_rel_path(template,self.template_type)

        if template not in asset_routes:
            raise TemplateNotFoundError(template)

        return {'template':template}
        
class TemplateQueryPipe(TemplateParamsPipe):
    def __init__(self,*allowed_assets:RouteAssetType):
        super().__init__(None)
        self.allowed_assets = list(allowed_assets)

    def pipe(self, asset:str,template:str):
        self.assetService.check_asset(asset,self.allowed_assets)
        self.template_type = asset #BUG 
        return super().pipe(template)

class CeleryTaskPipe(Pipe):
    
    def __init__(self):
        super().__init__(True)
        self.celeryService = Get(CeleryService)
    
    def pipe(self,scheduler:SchedulerModel):
        scheduler.task_name = task_name(scheduler.task_name)
        
        if scheduler.task_type != 'now' and scheduler.task_type != 'once':
            rules_keys = SCHEDULER_VALID_KEYS[scheduler.task_type]
            s_keys = set(scheduler.task_option.keys())
            if len(s_keys) == 0:
                raise CelerySchedulerOptionError
            if len(s_keys.difference(rules_keys)) != 0:
                raise CelerySchedulerOptionError
        
        setattr(scheduler,'heaviness' , self.celeryService._task_registry[scheduler.task_name]['heaviness'])
        return {'scheduler':scheduler}
    
class ContactsIdPipe(Pipe):
        @InjectInMethod
        def __init__(self, contactsService:ContactsService):
            super().__init__(True)
            self.contactsService = contactsService

        def pipe(self,contact_id:str):
            # TODO check if it is 
            return {'contact_id':contact_id}

class RelayPipe(Pipe):

    def __init__(self,parse_email=True):
        super().__init__(True)
        self.parse_email = parse_email

    def pipe(self,relay:str):
        if relay==None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail='Relay not specified')

        if relay != 'sms' and relay != 'email':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail='Relay not allowed')
        
        if relay=='email' and self.parse_email:
            relay = 'html'

        return {'relay':relay}
    

class TwilioFromPipe(Pipe):

    def __init__(self, phone_number_name:str):
        super().__init__(True)
        self.twilioService:TwilioService = Get(TwilioService)
        self.configService = Get(ConfigService)

        self.phone_number = self.configService[phone_number_name]
    
    def pipe(self,scheduler:SchedulerModel=None,otpModel:OTPModel=None):

        if scheduler!= None:
            content = scheduler.content
            content.from_ = self.setFrom_(content.from_)
            content.to = self.twilioService.parse_to_phone_format(content.to)
            return {'scheduler':scheduler}

        if otpModel != None:
            otpModel.to = self.twilioService.parse_to_phone_format(otpModel.to)
            otpModel.from_ = self.setFrom_(otpModel.from_)
            return {'otpModel':otpModel}
        
        return {}

    def setFrom_(self,from_):
        if from_ == None:
            return  self.phone_number
        return self.twilioService.parse_to_phone_format(from_)
        
        


class AuthClientPipe(Pipe):

    @InjectInMethod
    def __init__(self,jwtAuthService:JWTAuthService):
        super().__init__(True)
        self.jwtAuthService = jwtAuthService
    
    def pipe(self,client:str,scope:str):
        return {'client':client,'scope':scope}
    

class ForceClientPipe(Pipe):

    def __init__(self):
        super().__init__(True)

    def pipe(self, client: ClientORM):

        if client == None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client information is missing or invalid.")

        return {'client': client}
    
class ForceGroupPipe(Pipe):

    def __init__(self):
        super().__init__(True)

    def pipe(self, group: GroupClientORM):
        if group == None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group information is missing or invalid.")

        return {'group': group}

class RefreshTokenPipe(Pipe):

    def __init__(self,):
        super().__init__(True)
        self.jwtAuthService:JWTAuthService = Get(JWTAuthService)
    
    async def pipe(self,tokens:TokensModel):
        tokens = tokens.tokens
        tokens = self.jwtAuthService.verify_refresh_permission(tokens)
        return {'tokens':tokens}
    
class ContactStatusPipe(Pipe):
 
    def __init__(self):
        super().__init__(True)
        
    def pipe(self,next_status:str):
        allowed_status = Status._member_names_.copy() 
        allowed_status.remove(Status.Active.value)
        next_status = next_status.capitalize()

        if next_status not in allowed_status:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Next status query is not valid")

        next_status:Status = Status._member_map_[next_status]
        return {'next_status':next_status}
    

class OffloadedTaskResponsePipe(Pipe):

    def __init__(self, copy_res=False):
        super().__init__(False)
        self.copy_res = copy_res

    def pipe(self, result: Any | Response, response: Response = None, scheduler: SchedulerModel = None, otpModel: OTPModel = None, taskManager: TaskManager = None, as_async: bool = None):
        as_async = self._determine_async(taskManager, as_async)
        result = self._process_result(result, taskManager)
        response = self._prepare_response(result, response)
        
        self._set_status_code(response, scheduler, otpModel, as_async)
        return response

    def _determine_async(self, taskManager: TaskManager, as_async: bool) -> bool:
        if taskManager is None and as_async is None:
            return False
        if taskManager is not None:
            return taskManager.meta['as_async']
        return as_async if as_async is not None else False

    def _process_result(self, result: Any|Response, taskManager: TaskManager) -> Any | Response:
        
        if (result == None or result.body == b'{}' or result.body == b'') and taskManager is not None:
            return taskManager.results
        return result

    def _prepare_response(self, result: Any | Response, response: Response) -> Response:
        if not isinstance(result, Response):
            result = JSONResponse(content=result)
            if self.copy_res:
                response = copy_response(result, response)
            else:
                response = result
        else:
            response = result
        return response

    def _set_status_code(self, response: Response, scheduler: SchedulerModel, otpModel: OTPModel, as_async: bool):
        if (scheduler and scheduler.task_type != TaskType.NOW.value) or (otpModel and as_async) or as_async:
            response.status_code = 201
        else:
            response.status_code = 200


class KeepAliveResponsePipe(Pipe):
    def __init__(self, before):
        super().__init__(before)
    
    def pipe(self, result:Any|Response,keepAliveConn:KeepAliveQuery):
        keepAliveConn.dispose()
        # TODO add headers and status code
        return result
    

class TwilioResponseStatusPipe(Pipe):
    def __init__(self,before=False,status_code=status.HTTP_204_NO_CONTENT):
        super().__init__(before)
        self.status_code=status_code

    def pipe(self,result:Any|Response,response:Response):
        response.status_code = self.status_code
        return result    

@AsyncAPIFilterInject
async def parse_phone_number(phone_number:str) -> str:
    """
    Parse the phone number to the E.164 format.
    """
    twilioService:TwilioService = Get(TwilioService)
    phone_number= twilioService.parse_to_phone_format(phone_number)       
    return {
        'phone_number':phone_number
    }



@APIFilterInject
def verify_email_pipe(email:str):
    if not email_validator(email):
            raise EmailInvalidFormatError(email)
    return {
        'email':email
    }

@APIFilterInject
async def force_task_manager_attributes_pipe(taskManager:TaskManager):
    taskManager.return_results = True
    taskManager.meta['save_result'] =False
    taskManager.meta['runtype'] = 'sequential'

    return {'taskManager':taskManager}

class ContactToInfoPipe(Pipe):

    def __init__(self,info_key:str,parse_key:str,interrupt_if_none:bool=False,callback:Callable=None,split:str='.' ):
        super().__init__(True)
        self.info_key= info_key
        self.interrupt_if_none = interrupt_if_none
        self.callback = callback
        self.iterator = parse_key.split(split)
    
    async def pipe(self,scheduler:SchedulerModel):
        
        filtered_content = []
        # if scheduler.sender_type =='raw':
        #     return {}
        
        for content in scheduler.content:
            ptr = content
            for sk in self.iterator[:-1]:
                next_ptr =getattr(ptr,sk,None) 
                if next_ptr == None:
                    ...
                ptr = next_ptr
            
            
            if ptr == None:
                ...
            
            if not getattr(ptr,'as_contact',False):
                continue

            val = getattr(ptr,self.iterator[-1],None)
            
            if val== None:
                ...

            async def getter(val):
                contact:ContactSummary = await ContactSummaryORMCache.Cache(val)
                if contact == None:
                    ...
                piped_info_key = contact.get(self.info_key,None)
                if piped_info_key == None:
                    ...
                else:
                    return piped_info_key

            if isinstance(val,str):
                val = await getter(val)
            
            elif isinstance(val,list):
                val = [await getter(v) for v in val]
            else:
                ...
            
            setattr(ptr,self.iterator[-1],val)
            print(ptr)
        return {}
        