from dataclasses import asdict
import json
from typing import Any, Callable, Coroutine, Literal, Optional, Type, get_args
from beanie import Document
from fastapi import HTTPException, Request, Response,status
from app.classes.auth_permission import AuthPermission, TokensModel
from app.classes.broker import exception_to_json
from app.classes.celery import AlgorithmType, SchedulerModel,TaskType
from app.classes.email import EmailInvalidFormatError
from app.classes.template import Extension, HTMLTemplate, Template, TemplateAssetError, TemplateNotFoundError
from app.container import Get, InjectInMethod
from app.definition._service import BaseMiniService, BaseMiniServiceManager
from app.depends.class_dep import ObjectsSearch
from app.errors.contact_error import ContactMissingInfoKeyError, ContactNotExistsError
from app.errors.service_error import MiniServiceStrictValueNotValidError, ServiceNotAvailableError
from app.manager.task_manager import TaskManager
from app.models.call_model import CallCustomSchedulerModel
from app.models.contacts_model import Status, SubscriptionORM
from app.models.email_model import BaseEmailSchedulerModel
from app.models.otp_model import OTPModel
from app.models.security_model import ClientORM, GroupClientORM
from app.models.sms_model import SMSCustomSchedulerModel
from app.services.worker.celery_service import CeleryService, ChannelMiniService
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.file.file_service import FileService
from app.services.security_service import JWTAuthService
from app.definition._utils_decorator import Pipe
from app.ntfr_tasks import TASK_REGISTRY, task_name
from app.services.worker.arq_service import ArqDataTaskService
from app.utils.constant import SpecialKeyAttributesConstant
from app.utils.helper import DICT_SEP, AsyncAPIFilterInject, PointerIterator, copy_response, issubclass_of, parseToBool
from app.utils.validation import email_validator, phone_number_validator
from app.depends.orm_cache import ContactSummaryORMCache
from app.models.contacts_model import ContactSummary
from app.services.database.object_service import Object,DeleteError,ObjectWriteResult
from app.utils.globals import CAPABILITIES

async def to_otp_path(template:str):
    template = "otp/" + template
    return {'template':template}


class RegisterSchedulerPipe(Pipe):
    def __init__(self,algorithm:AlgorithmType=None):
        super().__init__(True)
        if algorithm and algorithm not in get_args(AlgorithmType):
            raise ValueError('Algorithm not allowed')
            
        self.algorithm = algorithm

    async def pipe(self,scheduler:SchedulerModel,taskManager:TaskManager):
        taskManager.register_scheduler(scheduler)
        if self.algorithm:
            taskManager.meta['algorithm'] = self.algorithm
        return {}

if CAPABILITIES['object']:
    from app.services.assets_service import AssetService, AssetType, AssetTypeNotAllowedError, RouteAssetType, DIRECTORY_SEPARATOR

    class TemplateParamsPipe(Pipe):
        
        asset_routes_key='asset_routes'

        def __init__(self,template_type:RouteAssetType=None,extension:str=None,accept_none=False,inject_asset_routes=False):
            super().__init__(True)
            self.assetService= Get(AssetService)
            self.configService = Get(ConfigService)
            self.template_type = template_type
            self.extension = extension
            self.accept_none = accept_none
            self.inject_asset_routes = inject_asset_routes

        async def pipe(self,template:str):
                if template == '' and self.accept_none:
                    return {'template':template}
                
                if self.extension:
                    template+="."+self.extension
                
                if self.template_type:
                    asset_routes = self.assetService.exportRouteName(self.template_type)
                    template = self.assetService.asset_rel_path(template,self.template_type)
                else: 
                    asset_routes = self.assetService.get_assets_dict_by_path(template)
                            
                if template not in asset_routes:
                    raise TemplateNotFoundError(template)

                if self.inject_asset_routes:
                    return asset_routes
                
                return {'template':template}
            
    class TemplateSignatureQueryPipe(TemplateParamsPipe):
        def __init__(self):
            super().__init__('email', 'html', False)

        async def pipe(self,scheduler: BaseEmailSchedulerModel):
            if scheduler.signature == None:
                return {}
            val:dict =  await super().pipe(scheduler.signature.template)
            scheduler.signature.template = val['template']
            return {}
            
    class InjectTemplateInterface:


        def __init__(self,assetService:AssetService,template_type:RouteAssetType,will_validate:bool):
            self.assetService = assetService
            self.template_type = template_type
            self.will_validate= will_validate


        def _inject_template(self,template:str):
            assets = getattr(self.assetService,self.template_type,None)
            if assets == None:
                raise TemplateAssetError
            
            return assets[template]

    class TemplateValidationInjectionPipe(Pipe,PointerIterator,InjectTemplateInterface):
        
        SCHEDULER_TEMPLATE_ERROR_KEY = 'template'

        def __init__(self,template_type:RouteAssetType ,data_key:str,index_key:str='', will_validate:bool = True,split:str='.'):
            super().__init__(True)
            PointerIterator.__init__(self,data_key,split)
            self.template_type=template_type
            self.will_validate= will_validate
            index_key = 'index' if not index_key else index_key+'.index'
            InjectTemplateInterface.__init__(self,Get(AssetService),template_type,will_validate)
            self.index_ptr = PointerIterator(index_key,split)
            
        async def pipe(self,template:str,scheduler:SchedulerModel)->Template:

                template = self._inject_template(template)
                filtered_content =[]

                if self.will_validate:
                    for content in scheduler.content:
                        ptr = self.ptr(content)
                        idx_ptr = self.index_ptr.ptr(content)  
                        if ptr == None:
                            ...

                        val = ptr.get_val()
                        index = idx_ptr.get_val()
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
                                
                    if scheduler.filter_error:
                        scheduler.content = filtered_content
                                    
                return {'template':template,'scheduler':scheduler}
        
    class FilterAllowedSchemaPipe(Pipe):

        @InjectInMethod()
        def __init__(self,assetService:AssetService):
            super().__init__(False)
            self.assetService = assetService
        
        def pipe(self,result:dict[str,dict],authPermission:AuthPermission):
            if authPermission == None:
                return result
            temp_res = {}
            for path,schema in result.items():
                try:
                    self.assetService._raw_verify_asset_permission(authPermission,path)
                    temp_res[path]=schema
                except:
                    continue
            
            return temp_res

    class ObjectS3OperationResponsePipe(Pipe):
            
        def __init__(self,):
            super().__init__(False)

        def pipe(self,result:dict):
            meta:Object|list[Object]|None = result.get('meta',[]) 
            more_meta= type(meta) == list
            write_result:ObjectWriteResult = result.get('result',None)

            errors = [{
                    "object_name": getattr(e, "object_name", None),
                    "version_id": getattr(e, "version_id", None),
                    "code": getattr(e, "code", None),
                    "message": getattr(e, "message", None)} for e in result.get('errors',[]) ]
            
            write_result = {"bucket_name": write_result.bucket_name,
                    "object_name": write_result.object_name,
                    "version_id": write_result.version_id,
                    "etag": write_result.etag,
                    "last_modified":write_result.last_modified.isoformat(),
                    "location":write_result.location,
                    "http_headers": write_result.http_headers} if  write_result != None else {}

            
            if meta:
                if not more_meta:   
                    meta=[meta]

                def parse_meta(m):
                    m:dict = asdict(m)
                    m['is_latest'] = parseToBool(m['is_latest'])
                    m['last_modified'] = m['last_modified'].isoformat()
                    if 'metadata' in m:
                        m['metadata'] = dict(m['metadata'])
                    m.pop('storage_class',None), m.pop('owner_id',None), m.pop('owner_name',None), m.pop('is_dir',None)
                    return m
                meta = [parse_meta(m) for m in meta]

                if not more_meta:
                    meta=meta[0]
                
            return {
                'meta':meta,
                'errors':errors,
                'result':write_result,
                'content': result.get('content',"")
            }

    class ValidFreeInputTemplatePipe(Pipe):

        allowed_assets = tuple(AssetType._value2member_map_.keys())
        allowed_extension = set(['.'+k for k in  Extension._value2member_map_.keys()])

        def __init__(self, accept_empty=True,accept_dir=True,allowed_extension=None,allowed_assets=None):
            super().__init__(True)
            self.fileService = Get(FileService)
            self.accept_empty=accept_empty
            self.accept_dir = accept_dir
            self._allowed_extension = self.allowed_extension if allowed_extension == None else allowed_extension
            self._allowed_assets = self.allowed_assets if allowed_assets == None else allowed_assets


        def pipe (self,template:str,objectsSearch:ObjectsSearch):
            if template != '': # if the template input is not empty
                if not template.startswith(self._allowed_assets):
                    raise AssetTypeNotAllowedError
                if not self.fileService.is_file(template,False,self._allowed_extension) and not self.accept_dir:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST,'Directory Not allowed')
                
                objectsSearch.is_file = self.fileService.soft_is_file(template)
                if not objectsSearch.is_file and objectsSearch.version_id:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST,'There is no version on prefix')

            else: # the template is empty
                if not self.accept_empty:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST,'Object name cannot be empty')
                objectsSearch.is_file = False
        
            return {}

class CeleryTaskPipe(Pipe):
    
    def __init__(self):
        super().__init__(True)
        self.celeryService = Get(CeleryService)
    
    def pipe(self,scheduler:SchedulerModel,taskManager:TaskManager,channel:ChannelMiniService):
        if scheduler.task_option:
            scheduler.task_option._ignore_result = not taskManager.meta.get('save_result',False)
            scheduler.task_option._retry = taskManager.meta.get('retry',False)
            scheduler.task_option._queue = channel.queue
        
        scheduler.task_name = task_name(scheduler.task_name)
        scheduler._heaviness = TASK_REGISTRY[scheduler.task_name]['heaviness']
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
            ...

        return {'relay':relay}

if  CAPABILITIES['twilio']: 
    from app.services.ntfr.twilio_service import TwilioAccountMiniService, TwilioService
    class TwilioPhoneNumberPipe(Pipe):

        PhoneNumberChoice = Literal['default','otp','chat','auto-mess']

        def __init__(self, phone_number_name:PhoneNumberChoice ='default',fallback=False):
            super().__init__(True)
            self.twilioService:TwilioService = Get(TwilioService)
            self.configService = Get(ConfigService) 
            if phone_number_name not in get_args(self.PhoneNumberChoice):
                raise ValueError('Phone Number name not valid')
            
            self.fallback= fallback
            self.phone_number_name = phone_number_name
        
        def pipe(self,twilio:TwilioAccountMiniService,scheduler:SMSCustomSchedulerModel | CallCustomSchedulerModel =None,otpModel:OTPModel=None,):

            if scheduler!= None:
                for content in scheduler.content:
                    content._from = self.setFrom_(twilio)
                    if not content.sender_type == 'raw':
                        content.to = [self.twilioService.parse_to_phone_format(to) for to in content.to]
                return {'scheduler':scheduler}

            if otpModel != None:
                otpModel.to = self.twilioService.parse_to_phone_format(otpModel.to)
                otpModel._from = self.setFrom_(twilio)
                return {'otpModel':otpModel}
            
            return {}

        def setFrom_(self,twilio:TwilioAccountMiniService):
            pn=None
            match self.phone_number_name:
                case 'default':
                    return twilio.depService.model.from_number  
                
                case 'otp':
                    pn= twilio.depService.model.twilio_otp_number
                
                case 'chat':
                    pn= twilio.depService.model.twilio_chat_number
                
                case 'auto-mess':
                    pn= twilio.depService.model.twilio_automated_response_number

                case _:
                    ...

            if pn == None:
                if self.fallback:
                    return twilio.depService.model.from_number

                raise ServiceNotAvailableError(f'The {twilio.miniService_id} profile does not have {self.phone_number_name} set')
            
            return pn
        
    async def parse_phone_number(phone_number:str) -> str:
        """
        Parse the phone number to the E.164 format.
        """
        twilioService:TwilioService = Get(TwilioService)
        phone_number= twilioService.parse_to_phone_format(phone_number)       
        return {
            'phone_number':phone_number
        }
            
class AuthClientPipe(Pipe):

    @InjectInMethod()
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

    def pipe(self, result: Any | Response, response: Response = None, scheduler: SchedulerModel = None, otpModel: OTPModel = None, taskManager: TaskManager = None, background: bool = None):
        background = self._determine_async(taskManager, background)
        result = self._process_result(result, taskManager)
        self._set_status_code(response, scheduler, otpModel, background)
        return result

    def _determine_async(self, taskManager: TaskManager, background: bool) -> bool:
        if taskManager is None and background is None:
            return False
        if taskManager is not None:
            return taskManager.meta['background']
        return background if background is not None else False

    def _process_result(self, result: Any|Response, taskManager: TaskManager) -> Any | Response:
        
        if result == None  and taskManager is not None:
            return taskManager.results
        return result

    def _set_status_code(self, response: Response, scheduler: SchedulerModel, otpModel: OTPModel, background: bool):
        if (scheduler and scheduler.task_type != TaskType.NOW) or (otpModel and background) or background:
            response.status_code = 201
        else:
            response.status_code = 200
    
class TwilioResponseStatusPipe(Pipe):
    def __init__(self,before=False,status_code=status.HTTP_204_NO_CONTENT):
        super().__init__(before)
        self.status_code=status_code

    def pipe(self,result:Any|Response,response:Response):
        response.status_code = self.status_code
        return result    


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
            
            val = ptr.get_val()
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

class ContentIndexPipe(Pipe,PointerIterator):

    def __init__(self, var:str=None):
        super().__init__(True)
        var = 'index' if not var else var+'.index'
        PointerIterator.__init__(self,var)
        self.configService = Get(ConfigService)

    def pipe(self,scheduler:SchedulerModel,taskManager:TaskManager):
        if taskManager.meta['split']: # TODO check whether i am in a pool or not
            return {'scheduler':scheduler}

        for i,content in enumerate(scheduler.content):
            ptr = self.ptr(content)
            index = ptr.get_val()
            val =  index if index != None else i
            ptr.set_val(val)
        
        return {'scheduler':scheduler}

class  GlobalPointerIteratorPipe(Pipe):

    def __init__(self,separator:str):
        super().__init__(True)
        self.sep= separator
    
    def pipe(self,globalIter:str|None):
        if globalIter != None:
            globalIter = PointerIterator(globalIter,self.sep,dict)

        return {'globalIter':globalIter}

class DocumentFriendlyPipe(Pipe):

    def __init__(self, include:set=None,exclude:set=None,exclude_none=False,exclude_defaults=False):
        super().__init__(False)
        self.include = set() if include == None else include
        self.exclude = set() if exclude == None else exclude
        self.exclude_none = exclude_none
        self.exclude_defaults = exclude_defaults

    def pipe(self,result:Document|list[Document]):
        is_list = isinstance(result,list)
        temp = []
        if not is_list:
            result=[result]
        
        for r in result:
            result_id = str(r.id)
            
            dump_kwargs = {'mode': 'json'}
            if self.include:
                dump_kwargs['include'] = self.include
            if self.exclude:
                dump_kwargs['exclude'] = self.exclude

            dump_kwargs['exclude_none'] = self.exclude_none
            dump_kwargs['exclude_defaults'] = self.exclude_defaults

            r = r.model_dump(**dump_kwargs)
            r['id'] =result_id

            temp.append(r)
        
        if is_list:
            return temp
    
        return temp[0]

class ObjectRelationalFriendlyPipe(Pipe):

    def __init__(self,):
        super().__init__(False)
    
    def pipe(self,result):
        if hasattr(result,'to_json'):
            return result.to_json
        return None

class MiniServiceInjectorPipe(Pipe):
    def __init__(self,cls:Type[BaseMiniServiceManager],key:str='profile',strict_value:str=None):
        super().__init__(True)
        if not issubclass_of(BaseMiniServiceManager,cls):
            raise TypeError('Must be a Mini Service Manager')

        self.service:BaseMiniServiceManager = Get(cls)  
        self.key = key
        self.strict_value =strict_value

    def pipe(self,profile:str):
        if self.strict_value != None and profile== self.strict_value:
            miniService:BaseMiniService = getattr(self.service,self.strict_value)
            if miniService == None:
                raise MiniServiceStrictValueNotValidError
            return {
                self.key:miniService,
                'profile':miniService.miniService_id
            }

        return {
            self.key: self.service.MiniServiceStore.get(profile)
            }

    
class ArqJobIdPipe(Pipe):

    @InjectInMethod()
    def __init__(self,arqService:ArqDataTaskService):
        super().__init__(True)
        self.arqService = arqService
    
    def pipe(self,job_id:str): return {'job_id':self.arqService.compute_job_id(job_id)}



class DataClassToDictPipe(Pipe):

    def __init__(self,silent:bool=True):
        super().__init__(False)
        self.silent = silent
    
    def pipe(self,result:Any):
        if isinstance(result,list):
            return [asdict(r) for r in result]
        else:
            return asdict(result)

class JSONLoadsPipe(Pipe):
    def __init__(self,silent:bool=True):
        super().__init__(False)
        self.silent = silent

    def pipe(self,result:list[str]|str):
        if isinstance(result,list):
            return [json.loads(r) for r in result]
        elif isinstance(result,str):
            return json.loads(result)
        else:
            if not self.silent:
                raise TypeError
            return result