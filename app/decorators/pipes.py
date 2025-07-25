from typing import Any, Callable, Coroutine, Literal

from fastapi import HTTPException, Request, Response,status
from fastapi.responses import JSONResponse
from app.classes.auth_permission import AuthPermission, TokensModel
from app.classes.broker import exception_to_json
from app.classes.celery import SchedulerModel,CelerySchedulerOptionError,SCHEDULER_VALID_KEYS, TaskType
from app.classes.email import EmailInvalidFormatError
from app.classes.template import Template, TemplateAssetError, TemplateNotFoundError
from app.container import Get, InjectInMethod
from app.depends.class_dep import KeepAliveQuery
from app.errors.contact_error import ContactMissingInfoKeyError, ContactNotExistsError
from app.models.call_model import CallCustomSchedulerModel
from app.models.contacts_model import Status, SubscriptionORM
from app.models.otp_model import OTPModel
from app.models.security_model import ClientORM, GroupClientORM
from app.models.sms_model import OnGoingSMSModel, SMSCustomSchedulerModel
from app.services.assets_service import AssetService, RouteAssetType, DIRECTORY_SEPARATOR, REQUEST_DIRECTORY_SEPARATOR
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.security_service import JWTAuthService
from app.definition._utils_decorator import Pipe
from app.services.celery_service import CeleryService, TaskManager, task_name
from app.services.twilio_service import TwilioService
from app.utils.constant import SpecialKeyAttributesConstant
from app.utils.helper import DICT_SEP, AsyncAPIFilterInject, PointerIterator, copy_response
from app.utils.validation import email_validator, phone_number_validator
from app.utils.helper import APIFilterInject
from app.depends.variables import parse_to_phone_format
from app.depends.orm_cache import ContactSummaryORMCache
from app.models.contacts_model import ContactSummary

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
    
    async def pipe(self,template:str):
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

        def __init__(self, ):
            super().__init__(True)
            self.contactsService = Get(ContactsService)

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
    

class TwilioPhoneNumberPipe(Pipe):

    def __init__(self, phone_number_name:str):
        super().__init__(True)
        self.twilioService:TwilioService = Get(TwilioService)
        self.configService = Get(ConfigService)

        self.phone_number = self.configService[phone_number_name]
    
    def pipe(self,scheduler:SMSCustomSchedulerModel | CallCustomSchedulerModel =None,otpModel:OTPModel=None):

        if scheduler!= None:
            for content in scheduler.content:
                content.from_ = self.setFrom_(content.from_)
                if not content.sender_type == 'raw':
                    content.to = [self.twilioService.parse_to_phone_format(to) for to in content.to]
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

async def parse_phone_number(phone_number:str) -> str:
    """
    Parse the phone number to the E.164 format.
    """
    twilioService:TwilioService = Get(TwilioService)
    phone_number= twilioService.parse_to_phone_format(phone_number)       
    return {
        'phone_number':phone_number
    }

async def verify_email_pipe(email:str):
    if not email_validator(email):
            raise EmailInvalidFormatError(email)
    return {
        'email':email
    }

async def force_task_manager_attributes_pipe(taskManager:TaskManager):
    taskManager.return_results = True
    taskManager.meta['save_result'] =False
    taskManager.meta['runtype'] = 'sequential'

    return {'taskManager':taskManager}

class ContactToInfoPipe(Pipe,PointerIterator):

    def __init__(self,info_key:str,parse_key:str,callback:Callable=None,split:str='.' ):
        super().__init__(True)
        self.info_key= info_key
        self.callback = callback
        PointerIterator.__init__(self,parse_key,split=split)
    
    async def get_info_key(self,val,filter_error):
        contact:ContactSummary = await ContactSummaryORMCache.Cache(val,val)
        if contact == None:
            if not filter_error:
                raise ContactNotExistsError(val)
            else:
                return None
        piped_info_key = contact.get(self.info_key,None)
        if piped_info_key == None:
            if not filter_error:
                raise ContactMissingInfoKeyError(self.info_key)
            else:
                return None
        else:
            return piped_info_key
    
    async def pipe(self,scheduler:SchedulerModel):
        
        filtered_content = []
        
        for content in scheduler.content:
            
            ptr = self.ptr(content)  
            if ptr == None:
                ...
            
            if getattr(ptr,'sender_type','raw') =='raw':
                if scheduler.filter_error:
                    filtered_content.append(content)
                continue
            
            val = self.get_val(ptr)
            index = getattr(ptr,'index')  
            
            if getattr(ptr, 'sender_type', 'raw') == 'subs':
                subscriptions = await SubscriptionORM.filter(content_id=val).select_related('contact')
                contact_ids = [subscription.contact.contact_id for subscription in subscriptions if subscription.contact]
                if not contact_ids:
                    scheduler._errors[index] = {
                        'message':'No contact associated with this content subscriptions',
                        'index':index,
                        'key':val
                    }
                    continue
                val = contact_ids
                setattr(ptr, 'sender_type', 'raw')
            
            if val== None:
                ...

            if isinstance(val,str):
                contact_id = val
                val = await self.get_info_key(val,scheduler.filter_error)
                if val == None:
                    if scheduler.filter_error:
                        scheduler._errors[index] = {
                            'message':'Could not get info for the contact, might not exists or might not have set the needed info',
                            'index':index,
                            'key':contact_id
                        }
                    continue
            
            elif isinstance(val,list):
                contact_id = val
                temp = []
                errors= []
                for v in val:
                    t = await self.get_info_key(v,scheduler.filter_error)
                    if t ==None:
                        if scheduler.filter_error:
                            errors.append(v)
                        continue
                    temp.append(t)
                val = temp

                if errors:
                    scheduler._errors[index] ={
                        'message':'Could not get info for the contact, might not exists or might not have set the needed info',
                        'index':index,
                        'key':contact_id
                    }

            else:
                contact_id = None
            
            setattr(ptr,self.data_key,val)
            setattr(ptr,SpecialKeyAttributesConstant.CONTACT_SPECIAL_KEY_ATTRIBUTES,contact_id)
            if scheduler.filter_error:
                filtered_content.append(content)
        
        if len(filtered_content) > 0:
            scheduler.content = filtered_content
        
        return {'scheduler':scheduler}

class TemplateValidationInjectionPipe(Pipe,PointerIterator):
    
    SCHEDULER_TEMPLATE_ERROR_KEY = 'template'

    def __init__(self,template_type:RouteAssetType ,data_key:str,index_key:str, will_validate:bool = True,split:str='.'):
        super().__init__(True)
        PointerIterator.__init__(self,data_key,split)
        self.template_type=template_type
        self.will_validate= will_validate
        self.index_ptr = PointerIterator(index_key,split)
        self.assetService = Get(AssetService)
        
    async def pipe(self,template:str,scheduler:SchedulerModel)->Template:

            assets = getattr(self.assetService,self.template_type,None)
            if assets == None:
                raise TemplateAssetError
            
            template:Template = assets[template]
            filtered_content =[]

            if self.will_validate:
                for content in scheduler.content:
                    ptr = self.ptr(content)
                    idx_ptr = self.index_ptr.ptr(content)  
                    if ptr == None:
                        ...

                    val = self.get_val(ptr)
                    index = self.index_ptr.get_val(idx_ptr)
                    if val == None:
                        ...
                    
                    try:
                        val = template.validate(val)
                        if scheduler.filter_error:
                            filtered_content.append(content)
                    except Exception as e:
                        if not scheduler.filter_error:
                            raise e
                        else:
                            scheduler._errors[index] = {
                                'message':'Error while creating the template',
                                'error':exception_to_json(e),
                                'index':index
                            }
                            
                            
                
                if len(filtered_content) >0:
                    scheduler.content = filtered_content
                                
            return {'template':template,'scheduler':scheduler}

class ContentIndexPipe(Pipe,PointerIterator):

    def __init__(self, var:str=None):
        super().__init__(True)
        var = 'index' if not var else var+'.index'
        PointerIterator.__init__(self,var)

    def pipe(self,scheduler:SchedulerModel,taskManager:TaskManager):
        if taskManager.meta['split']:
            return {'scheduler':scheduler}

        for i,content in enumerate(scheduler.content):
            ptr = self.ptr(content)
            index = self.get_val(ptr)
            val =  index if index != None else i
            self.set_val(ptr,val)
        
        return {'scheduler':scheduler}




class  GlobalPointerIteratorPipe(Pipe):

    def __init__(self,separator:str):
        super().__init__(True)
        self.sep= separator
    
    def pipe(self,globalIter:str|None):
        if globalIter != None:
            globalIter = PointerIterator(globalIter,self.sep,dict)

        return {'globalIter':globalIter}
