from typing import Any
from fastapi import Depends, Request, Response
from app.classes.auth_permission import Role
from app.classes.celery import SchedulerModel, TaskHeaviness, TaskType
from app.classes.template import PhoneTemplate
from app.decorators.guards import CeleryTaskGuard, RegisteredContactsGuard
from app.decorators.handlers import CeleryTaskHandler, ServiceAvailabilityHandler, TemplateHandler, TwilioHandler
from app.decorators.permissions import JWTAssetPermission, JWTRouteHTTPPermission, TwilioPermission
from app.decorators.pipes import CeleryTaskPipe, OffloadedTaskResponsePipe, TemplateParamsPipe, TwilioFromPipe, _to_otp_path
from app.models.otp_model import OTPModel
from app.models.voice_model import BaseVoiceCallModel, CallStatusModel,OnGoingTwimlVoiceCallModel,OnGoingCustomVoiceCallModel
from app.services.celery_service import TaskService, CeleryService, OffloadTaskService
from app.services.chat_service import ChatService
from app.services.contacts_service import ContactsService
from app.services.logger_service import LoggerService
from app.services.twilio_service import  VoiceService
from app.definition._ressource import BaseHTTPRessource, BaseHTTPRessource, HTTPMethod, HTTPRessource, PingService, UseGuard, UseHandler, UseLimiter, UsePermission, UsePipe, UseRoles
from app.container import Get, InjectInMethod
from app.utils.dependencies import get_auth_permission, get_request_id
from app.decorators.my_depends import verify_twilio_token,as_async_query,populate_response_with_request_id



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
        self.offloadTaskService:OffloadTaskService = Get(OffloadTaskService)
        super().__init__()

    @UseLimiter(limit_value= '100/day')
    @UseRoles([Role.PUBLIC])
    @BaseHTTPRessource.Get('/balance/')
    def check_balance(self,request:Request,authPermission=Depends(get_auth_permission)):
        return self.voiceService.fetch_balance()

    @UseLimiter(limit_value='100/day')
    @UseRoles([Role.MFA_OTP])
    @UseHandler(TemplateHandler)
    @UsePipe(_to_otp_path)
    @UsePipe(TwilioFromPipe('TWILIO_OTP_NUMBER'),TemplateParamsPipe('phone','xml'))
    @BaseHTTPRessource.Post('/otp/{template}')
    def voice_relay_otp(self,template:str,otpModel:OTPModel,request:Request,authPermission=Depends(get_auth_permission)):
        phoneTemplate:PhoneTemplate = self.assetService.phone[template]
        _,body= phoneTemplate.build(otpModel.content,...)
        return self.voiceService.send_otp_voice_call(body,otpModel)
    
    @UseLimiter(limit_value='100/day')
    @UseRoles([Role.MFA_OTP])
    @UsePipe(TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @BaseHTTPRessource.Get('/otp/')
    async def enter_digit_otp(self,otpModel:OTPModel,request:Request,authPermission=Depends(get_auth_permission)):
        ...
    
    @UseLimiter(limit_value='100/day')
    @UseRoles([Role.RELAY])
    @UsePermission(JWTAssetPermission('phone'))
    @UseHandler(TemplateHandler,CeleryTaskHandler)
    @UsePipe(OffloadedTaskResponsePipe,before=False)
    @UsePipe(TemplateParamsPipe('phone','xml'),CeleryTaskPipe,TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @UseGuard(CeleryTaskGuard(['task_send_template_voice_call']))
    @BaseHTTPRessource.HTTPRoute('/template/{template}/',methods=[HTTPMethod.POST],dependencies=[Depends(populate_response_with_request_id)])
    async def voice_template(self,template:str,scheduler: CallTemplateSchedulerModel,request:Request,response:Response,authPermission=Depends(get_auth_permission),x_request_id:str= Depends(get_request_id),as_async:bool=Depends(as_async_query)):
        content = scheduler.content.model_dump()
        phoneTemplate:PhoneTemplate = self.assetService.phone[template]
        _,result = phoneTemplate.build(content,...)
        return await self.offloadTaskService.offload_task('normal',scheduler,True,3600,x_request_id,as_async,self.voiceService.send_template_voice_call,result,content)
    
    @UseLimiter(limit_value='50/day')
    @UseRoles([Role.RELAY])
    @UsePipe(CeleryTaskPipe,TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @UseGuard(CeleryTaskGuard(['task_send_twiml_voice_call']))
    @UseHandler(CeleryTaskHandler)
    @UsePipe(OffloadedTaskResponsePipe,before=False)
    @BaseHTTPRessource.HTTPRoute('/twiml/',methods=[HTTPMethod.POST],dependencies=[Depends(populate_response_with_request_id)],mount=False)
    async def voice_twilio_twiml(self,scheduler:CallTwimlSchedulerModel,request:Request,response:Response,authPermission=Depends(get_auth_permission),x_request_id:str= Depends(get_request_id),as_async:bool=Depends(as_async_query)):
        details = scheduler.content.model_dump(exclude={'url'})
        url = scheduler.content.url
        return await self.offloadTaskService.offload_task('normal',scheduler,True,3600,x_request_id,as_async,self.voiceService.send_twiml_voice_call,url,details)


    @UseLimiter(limit_value='50/day')
    @UseRoles([Role.RELAY])
    @UsePipe(CeleryTaskPipe,TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @UseGuard(CeleryTaskGuard(['task_send_custom_voice_call']))
    @UseHandler(CeleryTaskHandler)
    @UsePipe(OffloadedTaskResponsePipe,before=False)
    @BaseHTTPRessource.HTTPRoute('/custom/',methods=[HTTPMethod.POST],dependencies=[Depends(populate_response_with_request_id)])
    async def voice_custom(self,scheduler: CallCustomSchedulerModel,request:Request,response:Response,authPermission=Depends(get_auth_permission),x_request_id:str= Depends(get_request_id),as_async:bool=Depends(as_async_query)):
        details = scheduler.content.model_dump(exclude={'body','voice','language','loop'})
        body = scheduler.content.body
        voice=scheduler.content.voice
        lang=scheduler.content.language
        loop= scheduler.content.loop

        return await self.offloadTaskService.offload_task('normal',scheduler,True,3600,x_request_id,as_async,self.voiceService.send_custom_voice_call,body,voice,lang,loop,details)
    
    @UseLimiter(limit_value='50/day')
    @UseRoles([Role.MFA_OTP])
    @UseGuard(RegisteredContactsGuard)
    @BaseHTTPRessource.HTTPRoute('/authenticate/',methods=[HTTPMethod.GET])
    async def voice_authenticate(self,request:Request,authPermission=Depends(get_auth_permission)):
        ...
    
CALL_INCOMING_PREFIX = "call-incoming"

@UseRoles([Role.TWILIO])
@PingService([VoiceService])
@UseHandler(ServiceAvailabilityHandler,TwilioHandler)
#@UsePermission(TwilioPermission)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(CALL_INCOMING_PREFIX)
class IncomingCallRessources(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self, voiceService: VoiceService,chatService:ChatService,contactsService:ContactsService,loggerService:LoggerService) -> None:
        self.voiceService = voiceService
        self.chatService = chatService
        self.contactsService = contactsService
        self.loggerService = loggerService
        super().__init__(dependencies=[Depends(verify_twilio_token)])


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

