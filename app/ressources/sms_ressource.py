from typing import Annotated, Any, List
from fastapi import Depends, Header, Request
from pydantic import BaseModel
from app.classes.auth_permission import Role
from app.classes.celery import SchedulerModel, TaskType
from app.classes.template import SMSTemplate
from app.decorators.guards import CeleryTaskGuard
from app.decorators.handlers import CeleryTaskHandler, ServiceAvailabilityHandler, TwilioHandler
from app.decorators.permissions import JWTAssetPermission,JWTRouteHTTPPermission
from app.decorators.pipes import CeleryTaskPipe, TemplateParamsPipe, TwilioFromPipe
from app.definition._ressource import HTTPMethod, HTTPRessource, PingService, UseGuard, UseLimiter, UsePermission, BaseHTTPRessource, UseHandler, UsePipe, UseRoles
from app.container import InjectInMethod, InjectInFunction
from app.models.otp_model import OTPModel
from app.models.sms_model import OnGoingBaseSMSModel, OnGoingSMSModel, OnGoingTemplateSMSModel, SMSStatusModel
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

    @UseLimiter(limit_value="10000/minutes")
    @UsePipe(TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @UseRoles([Role.MFA_OTP])
    @BaseHTTPRessource.HTTPRoute('/otp/',methods=[HTTPMethod.POST])
    def sms_relay_otp(self,otpModel:OTPModel,request:Request,authPermission=Depends(get_auth_permission)):
        return self.smsService.send_otp(otpModel)
    
    
    @UseLimiter(limit_value="5000/minutes")
    @UseRoles([Role.RELAY])    
    @UseHandler(CeleryTaskHandler)
    @UsePipe(CeleryTaskPipe,TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @UseGuard(CeleryTaskGuard(task_names=['task_send_custom_sms']))
    @BaseHTTPRessource.HTTPRoute('/custom/',methods=[HTTPMethod.POST])
    def sms_simple_message(self,scheduler: SMSCustomSchedulerModel,request:Request,authPermission=Depends(get_auth_permission)):
        message = scheduler.content.model_dump()
        if scheduler.task_type == TaskType.NOW.value:
            return self.smsService.send_template_sms(message)
        return self.celeryService.trigger_task_from_scheduler(scheduler,message)

    
    @UseLimiter(limit_value="5000/minutes")
    @UseRoles([Role.RELAY])
    @UseHandler(CeleryTaskHandler)
    @UsePipe(TemplateParamsPipe('sms','xml'),CeleryTaskPipe,TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @UsePermission(JWTAssetPermission('sms'))
    @UseGuard(CeleryTaskGuard([' task_send_template_sms']))
    @BaseHTTPRessource.HTTPRoute('/template/{template}',methods=[HTTPMethod.POST])
    def sms_template(self,template:str,scheduler: SMSTemplateSchedulerModel,request:Request,authPermission=Depends(get_auth_permission)):
        sms_data = scheduler.content
        smsTemplate:SMSTemplate = self.assetService.sms[template]
        _,result=smsTemplate.build(self.configService.ASSET_LANG,sms_data.data)
        message = {'body':result,'to':sms_data.to,'from_':sms_data.from_}
        
        if scheduler.task_type == TaskType.NOW:
            return self.smsService.send_template_sms(message)
        return self.celeryService.trigger_task_from_scheduler(scheduler,message)
    

    def sms_get_message(self,):
        ...

    def sms_delete_message(self,):
        ...



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

    @BaseHTTPRessource.HTTPRoute('/menu/',methods=[HTTPMethod.POST])
    async def sms_menu(self,authPermission=Depends(get_auth_permission)):
        pass
    
    @UseRoles([Role.CHAT])
    @BaseHTTPRessource.HTTPRoute('/live-chat/',methods=[HTTPMethod.POST])
    async def sms_chat(self,authPermission=Depends(get_auth_permission)):
        pass

    @BaseHTTPRessource.HTTPRoute('/automate-response/',methods=[HTTPMethod.POST])
    async def sms_automated(self,authPermission=Depends(get_auth_permission)):
        pass
    
    @BaseHTTPRessource.HTTPRoute('/handler_fail/',methods=[HTTPMethod.POST])
    async def sms_primary_handler_fail(self,authPermission=Depends(get_auth_permission)):
        pass

    @BaseHTTPRessource.HTTPRoute('/status/',methods=[HTTPMethod.POST])
    async def sms_call_status_changes(self,status: SMSStatusModel,authPermission=Depends(get_auth_permission)):
        ...

    @BaseHTTPRessource.HTTPRoute('/error/',methods=[HTTPMethod.POST])
    async def sms_error(self,authPermission=Depends(get_auth_permission)):
        pass