from typing import Annotated, Any, List
from fastapi import Depends, Header
from pydantic import BaseModel
from app.classes.auth_permission import Role
from app.classes.celery import SchedulerModel, TaskType
from app.classes.template import SMSTemplate
from app.decorators.guards import CeleryTaskGuard
from app.decorators.handlers import CeleryTaskHandler, ServiceAvailabilityHandler, TwilioHandler
from app.decorators.permissions import JWTAssetPermission,JWTRouteHTTPPermission
from app.decorators.pipes import CeleryTaskPipe, TemplateParamsPipe, TwilioFromPipe
from app.definition._ressource import HTTPRessource, PingService, UseGuard, UseLimiter, UsePermission, BaseHTTPRessource, UseHandler, UsePipe, UseRoles
from app.container import InjectInMethod, InjectInFunction
from app.models.otp_model import OTPModel
from app.models.sms_model import OnGoingBaseSMSModel, OnGoingSMSModel, OnGoingTemplateSMSModel
from app.services.assets_service import AssetService
from app.services.celery_service import CeleryService
from app.services.chat_service import ChatService
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.twilio_service import SMSService
from app.utils.dependencies import get_auth_permission


SMS_ONGOING_PREFIX = 'sms-ongoing'

class SMSCustomSchedulerModel(SchedulerModel):
    content: OnGoingSMSModel

class SMSTemplateSchedulerModel(SchedulerModel):
    content: OnGoingTemplateSMSModel

@PingService([SMSService])
@UseHandler(ServiceAvailabilityHandler,TwilioHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(SMS_ONGOING_PREFIX)
class OnGoingSMSRessource(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self, smsService: SMSService,chatService:ChatService,contactService:ContactsService,configService:ConfigService,celeryService:CeleryService) -> None:
        super().__init__()
        self.smsService: SMSService = smsService
        self.chatService: ChatService = chatService
        self.contactService: ContactsService = contactService
        self.configService:ConfigService = configService
        self.celeryService: CeleryService = celeryService

    @UsePipe(TwilioFromPipe)
    @UseRoles([Role.MFA_OTP])
    @BaseHTTPRessource.HTTPRoute('/otp/')
    def sms_relay_otp(self,otpModel:OTPModel,authPermission=Depends(get_auth_permission)):
        return self.smsService.send_otp(otpModel)
    
    @UseRoles([Role.RELAY])    
    @UsePipe(CeleryTaskPipe,TwilioFromPipe)
    @UseGuard(CeleryTaskGuard(task_names=['task_send_custom_sms']))
    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.HTTPRoute('/custom/')
    def sms_simple_message(self,scheduler: SMSCustomSchedulerModel,authPermission=Depends(get_auth_permission)):
        message = scheduler.content.model_dump()
        if scheduler.task_type == TaskType.NOW:
            return self.smsService.send_template_sms(message)
        return self.celeryService.trigger_task_from_scheduler(scheduler,message)

    
    @UseHandler(CeleryTaskHandler)
    @UseRoles([Role.RELAY])
    @UseGuard(CeleryTaskGuard([' task_send_template_sms']))
    @UsePipe(TemplateParamsPipe('sms'),CeleryTaskPipe,TwilioFromPipe)
    @UsePermission(JWTAssetPermission('sms'))
    @BaseHTTPRessource.HTTPRoute('/template/{template}')
    def sms_template(self,template:str,scheduler: SMSTemplateSchedulerModel,authPermission=Depends(get_auth_permission)):
        sms_data = scheduler.content
        smsTemplate:SMSTemplate = self.assetService.sms[template]
        _,result=smsTemplate.build(self.configService.ASSET_LANG,sms_data.data)
        message = {'body':result,'to':sms_data.to,'from_':sms_data.from_}
        
        if scheduler.task_type == TaskType.NOW:
            return self.smsService.send_template_sms(message)
        return self.celeryService.trigger_task_from_scheduler(scheduler,message)



SMS_INCOMING_PREFIX = "sms-incoming"

@UseRoles([Role.TWILIO])
@PingService([SMSService])
@UseHandler(ServiceAvailabilityHandler,TwilioHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(SMS_INCOMING_PREFIX )
class IncomingSMSRessource(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self,smsService:SMSService,contactsService:ContactsService,chatService:ChatService) -> None:
        self.smsService: SMSService = smsService
        self.contactsService: ContactsService = contactsService
        self.chatService: ChatService = chatService
        super().__init__(dependencies=[Depends(self.smsService.verify_twilio_token)])

    @BaseHTTPRessource.HTTPRoute('/menu/',methods=['POST'])
    async def sms_menu(self,authPermission=Depends(get_auth_permission)):
        pass
    
    @UseRoles([Role.CHAT])
    @BaseHTTPRessource.HTTPRoute('/live-chat/',methods=['POST'])
    async def sms_chat(self,authPermission=Depends(get_auth_permission)):
        pass

    @BaseHTTPRessource.HTTPRoute('/automate-response/',methods=['POST'])
    async def sms_automated(self,authPermission=Depends(get_auth_permission)):
        pass
    
    @BaseHTTPRessource.HTTPRoute('/handler_fail/',methods=['POST'])
    async def sms_primary_handler_fail(self,authPermission=Depends(get_auth_permission)):
        pass

    @BaseHTTPRessource.HTTPRoute('/status/',methods=['POST'])
    async def sms_call_status_changes(self,authPermission=Depends(get_auth_permission)):
        ...

    @BaseHTTPRessource.HTTPRoute('/error/',methods=['POST'])
    async def sms_error(self,authPermission=Depends(get_auth_permission)):
        pass