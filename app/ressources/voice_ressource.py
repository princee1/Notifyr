from typing import Any
from fastapi import Depends, Request
from app.classes.auth_permission import Role
from app.classes.celery import SchedulerModel, TaskType
from app.classes.template import PhoneTemplate
from app.decorators.guards import CeleryTaskGuard, RegisteredContactsGuard
from app.decorators.handlers import CeleryTaskHandler, ServiceAvailabilityHandler, TemplateHandler, TwilioHandler
from app.decorators.permissions import JWTAssetPermission, JWTRouteHTTPPermission
from app.decorators.pipes import CeleryTaskPipe, TemplateParamsPipe, TwilioFromPipe
from app.models.otp_model import OTPModel
from app.models.voice_model import BaseVoiceCallModel, CallStatusModel,OnGoingTwimlVoiceCallModel,OnGoingCustomVoiceCallModel
from app.services.celery_service import CeleryService
from app.services.chat_service import ChatService
from app.services.contacts_service import ContactsService
from app.services.logger_service import LoggerService
from app.services.twilio_service import VoiceService
from app.definition._ressource import BaseHTTPRessource, BaseHTTPRessource, HTTPMethod, HTTPRessource, PingService, UseGuard, UseHandler, UsePermission, UsePipe, UseRoles
from app.container import Get, InjectInMethod, InjectInFunction
from app.utils.dependencies import get_auth_permission


CALL_ONGOING_PREFIX = 'call-ongoing'



class CallTemplateSchedulerModel(SchedulerModel):
    content: BaseVoiceCallModel

class CallTwimlSchedulerModel(SchedulerModel):
    content: OnGoingTwimlVoiceCallModel

class CallCustomSchedulerModel(SchedulerModel):
    content: OnGoingCustomVoiceCallModel

@PingService([VoiceService])
@UseHandler(ServiceAvailabilityHandler,TwilioHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(CALL_ONGOING_PREFIX)
class OnGoingCallRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self, voiceService: VoiceService,chatService:ChatService,contactsService:ContactsService) -> None:
        self.voiceService = voiceService
        self.chatService = chatService
        self.contactsService = contactsService
        self.celeryService: CeleryService = Get(CeleryService)
        super().__init__()

    @UseRoles([Role.CHAT])
    @BaseHTTPRessource.Get('/balance')
    def check_balance(self,request:Request,authPermission=Depends(get_auth_permission)):
        return self.voiceService.fetch_balance()

    @UseRoles([Role.MFA_OTP])
    @UsePipe(TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @BaseHTTPRessource.Post('/otp/')
    def voice_relay_otp(self,otpModel:OTPModel,authPermission=Depends(get_auth_permission)):
        pass
        
    @UseRoles([Role.MFA_OTP])
    @UsePipe(TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @BaseHTTPRessource.Get('/otp/')
    async def enter_digit_otp(self,otpModel:OTPModel,authPermission=Depends(get_auth_permission)):
        ...
    
    @UseRoles([Role.RELAY])
    @UsePermission(JWTAssetPermission('phone'))
    @UseHandler(TemplateHandler,CeleryTaskHandler)
    @UsePipe(TemplateParamsPipe('phone'),CeleryTaskPipe,TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @UseGuard(CeleryTaskGuard(['task_send_template_voice_call']))
    @BaseHTTPRessource.HTTPRoute('/template/{template}/',methods=[HTTPMethod.POST])
    def voice_template(self,template:str,scheduler: CallTemplateSchedulerModel,authPermission=Depends(get_auth_permission)):
        content = scheduler.content.model_dump()
        phoneTemplate:PhoneTemplate = self.assetService.phone[template]
        _,result = phoneTemplate.build(...,content)

        if scheduler.task_type == TaskType.NOW.value:
            return self.voiceService.send_template_voice_call(result,content)
        return self.celeryService.trigger_task_from_scheduler(scheduler,result,content)

    @UseRoles([Role.RELAY])
    @UsePipe(CeleryTaskPipe,TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @UseGuard(CeleryTaskGuard(['task_send_twiml_voice_call']))
    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.HTTPRoute('/twiml/',methods=[HTTPMethod.POST])
    def voice_twilio_twiml(self,scheduler:CallTwimlSchedulerModel,authPermission=Depends(get_auth_permission)):
        details = scheduler.content.model_dump(exclude={'url'})
        url = scheduler.content.url

        if scheduler.task_type == TaskType.NOW.value:
            return self.voiceService.send_twiml_voice_call(url,details)
        return self.celeryService.trigger_task_from_scheduler(scheduler,url,details)

    @UseRoles([Role.RELAY])
    @UsePipe(CeleryTaskPipe,TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @UseGuard(CeleryTaskGuard(['task_send_custom_voice_call']))
    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.HTTPRoute('/custom/',methods=[HTTPMethod.POST])
    def voice_custom(self,scheduler: CallCustomSchedulerModel,authPermission=Depends(get_auth_permission)):
        details = scheduler.content.model_dump(exclude={'body'})
        body = scheduler.content.body

        if scheduler.task_type == TaskType.NOW.value:
            return self.voiceService.send_custom_voice_call(body,details)
        return self.celeryService.trigger_task_from_scheduler(scheduler,body,details)
    
    @UseRoles([Role.MFA_OTP])
    @UseGuard(RegisteredContactsGuard)
    @BaseHTTPRessource.HTTPRoute('/authenticate/',methods=[HTTPMethod.GET])
    async def voice_authenticate(self,authPermission=Depends(get_auth_permission)):
        ...
    

CALL_INCOMING_PREFIX = "call-incoming"

@UseRoles([Role.TWILIO])
@PingService([VoiceService])
@UseHandler(ServiceAvailabilityHandler,TwilioHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(CALL_INCOMING_PREFIX)
class IncomingCallRessources(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self, voiceService: VoiceService,chatService:ChatService,contactsService:ContactsService,loggerService:LoggerService) -> None:
        self.voiceService = voiceService
        self.chatService = chatService
        self.contactsService = contactsService
        self.loggerService = loggerService
        super().__init__(dependencies=[Depends(self.voiceService.verify_twilio_token)])


    @BaseHTTPRessource.HTTPRoute('/menu/',methods=[HTTPMethod.POST])
    async def voice_menu(self,authPermission=Depends(get_auth_permission)):
        ...
    
    @UseRoles([Role.CHAT])
    @BaseHTTPRessource.HTTPRoute('/live-chat/',methods=[HTTPMethod.POST])
    async def voice_live_chat(self,authPermission=Depends(get_auth_permission)):
        pass

    @BaseHTTPRessource.HTTPRoute('/automate-response/',methods=[HTTPMethod.POST])
    async def voice_automate_response(self,authPermission=Depends(get_auth_permission)):
        pass

    @BaseHTTPRessource.HTTPRoute('/handler_fail/',methods=[HTTPMethod.POST])
    async def voice_primary_handler_fail(self,authPermission=Depends(get_auth_permission)):
        pass

    @BaseHTTPRessource.HTTPRoute('/status/',methods=[HTTPMethod.POST])
    async def voice_call_status(self,status:CallStatusModel,authPermission=Depends(get_auth_permission)):
        ...

    @BaseHTTPRessource.HTTPRoute('/error/',methods=[HTTPMethod.POST])
    async def voice_error(self,authPermission=Depends(get_auth_permission)):
        pass

