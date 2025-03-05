from typing import Literal

from fastapi import HTTPException,status
from app.classes.auth_permission import AuthPermission, TokensModel
from app.classes.celery import SchedulerModel,CelerySchedulerOptionError,SCHEDULER_VALID_KEYS, TaskType
from app.classes.template import TemplateNotFoundError
from app.container import Get, InjectInMethod
from app.models.otp_model import OTPModel
from app.models.sms_model import OnGoingSMSModel
from app.services.assets_service import AssetService, RouteAssetType, DIRECTORY_SEPARATOR, REQUEST_DIRECTORY_SEPARATOR
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.security_service import JWTAuthService
from app.definition._utils_decorator import Pipe
from app.services.celery_service import CeleryService, task_name
from app.services.twilio_service import TwilioService
from app.utils.validation import phone_number_validator

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
    
    def __init__(self,template_type:RouteAssetType,extension:str=None):
        super().__init__(True)
        self.assetService= Get(AssetService)
        self.configService = Get(ConfigService)
        self.template_type = template_type
        self.extension = extension
    
    def pipe(self,template:str):
        template+=self.extension
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
        self.template_type = asset
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

    def pipe(self,relay:str):
        if relay==None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail='Relay not specified')

        if relay != 'sms' and relay != 'email':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail='Relay not allowed')
        
        if relay=='email':
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
