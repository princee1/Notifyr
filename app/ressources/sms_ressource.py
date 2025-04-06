from fastapi import Depends, Header, Request, Response
from app.classes.auth_permission import Role
from app.classes.celery import SchedulerModel, TaskHeaviness, TaskType
from app.classes.template import SMSTemplate
from app.decorators.guards import CeleryTaskGuard
from app.decorators.handlers import CeleryTaskHandler, ServiceAvailabilityHandler, TemplateHandler, TwilioHandler
from app.decorators.permissions import JWTAssetPermission,JWTRouteHTTPPermission
from app.decorators.pipes import CeleryTaskPipe, OffloadedTaskResponsePipe, TemplateParamsPipe, TwilioFromPipe, _to_otp_path
from app.definition._ressource import HTTPMethod, HTTPRessource, PingService, UseGuard, UseLimiter, UsePermission, BaseHTTPRessource, UseHandler, UsePipe, UseRoles
from app.container import Get, GetDependsAttr, InjectInMethod, InjectInFunction
from app.models.otp_model import OTPModel
from app.models.sms_model import OnGoingBaseSMSModel, OnGoingSMSModel, OnGoingTemplateSMSModel, SMSStatusModel
from app.services.celery_service import TaskService, CeleryService, OffloadTaskService
from app.services.chat_service import ChatService
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.twilio_service import SMSService
from app.utils.dependencies import APIFilterInject, get_auth_permission, get_query_params, get_request_id
from app.decorators.my_depends import verify_twilio_token,populate_response_with_request_id,as_async_query


SMS_ONGOING_PREFIX = 'sms-ongoing'



class SMSCustomSchedulerModel(SchedulerModel):
    content: OnGoingSMSModel

class SMSTemplateSchedulerModel(SchedulerModel):
    content: OnGoingTemplateSMSModel


#@PingService([SMSService])
@UseHandler(ServiceAvailabilityHandler,TwilioHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(SMS_ONGOING_PREFIX)
class OnGoingSMSRessource(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self, smsService: SMSService,chatService:ChatService,contactService:ContactsService,configService:ConfigService,offloadService:OffloadTaskService) -> None:
        super().__init__()
        self.smsService: SMSService = smsService
        self.chatService: ChatService = chatService
        self.contactService: ContactsService = contactService
        self.configService:ConfigService = configService
        self.offloadService= offloadService

    @UseLimiter(limit_value="10000/minutes")
    @UseRoles([Role.MFA_OTP])
    @UsePipe(_to_otp_path)
    @UsePipe(TwilioFromPipe('TWILIO_OTP_NUMBER'),TemplateParamsPipe('sms','xml'))
    @UseHandler(TemplateHandler)
    #@UsePipe(OffloadedTaskResponsePipe,before=False)
    #@UsePermission(JWTAssetPermission('sms'))
    @BaseHTTPRessource.HTTPRoute('/otp/{template}',methods=[HTTPMethod.POST])
    async def sms_relay_otp(self,template:str,otpModel:OTPModel,request:Request,response:Response,authPermission=Depends(get_auth_permission)):
        smsTemplate:SMSTemplate = self.assetService.sms[template]
        _,body= smsTemplate.build(otpModel.content,...)
        result = self.smsService.send_otp(otpModel,body)
        return result
        

    @UseLimiter(limit_value="5000/minutes")
    @UseRoles([Role.RELAY,Role.MFA_OTP])    
    @UseHandler(CeleryTaskHandler)
    @UsePipe(CeleryTaskPipe,TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @UsePipe(OffloadedTaskResponsePipe,before=False)
    @UseGuard(CeleryTaskGuard(task_names=['task_send_custom_sms']))
    @BaseHTTPRessource.HTTPRoute('/custom/',methods=[HTTPMethod.POST],dependencies=[Depends(populate_response_with_request_id)])
    async def sms_simple_message(self,scheduler: SMSCustomSchedulerModel,request:Request,response:Response,authPermission=Depends(get_auth_permission),x_request_id:str= Depends(get_request_id),as_async:bool=Depends(as_async_query)):
        message = scheduler.content.model_dump()
        return await self.offloadService.offload_task('normal',scheduler,True,3600,x_request_id,as_async,'parallel',self.smsService.send_custom_sms,message)
        
    @UseLimiter(limit_value="5000/minutes")
    @UseRoles([Role.RELAY])
    @UseHandler(CeleryTaskHandler,TemplateHandler)
    @UsePipe(TemplateParamsPipe('sms','xml'),CeleryTaskPipe,TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @UsePipe(OffloadedTaskResponsePipe,before=False)
    @UsePermission(JWTAssetPermission('sms'))
    @UseGuard(CeleryTaskGuard(['task_send_template_sms']))
    @BaseHTTPRessource.HTTPRoute('/template/{template}',methods=[HTTPMethod.POST],dependencies=[Depends(populate_response_with_request_id)])
    async def sms_template(self,template:str,scheduler: SMSTemplateSchedulerModel,request:Request,response:Response,authPermission=Depends(get_auth_permission),x_request_id:str= Depends(get_request_id),as_async:bool=Depends(as_async_query)):
        sms_data = scheduler.content
        smsTemplate:SMSTemplate = self.assetService.sms[template]
        _,result=smsTemplate.build(self.configService.ASSET_LANG,sms_data.data)
        message = {'body':result,'to':sms_data.to,'from_':sms_data.from_}
        return await self.offloadService.offload_task('normal',scheduler,True,3600,x_request_id,as_async,'parallel',self.smsService.send_template_sms,message)


    async def sms_get_message(self,):
        ...

    async def sms_delete_message(self,):
        ...



SMS_INCOMING_PREFIX = "sms-incoming"

@UseRoles([Role.TWILIO])
@PingService([SMSService])
@UseHandler(ServiceAvailabilityHandler,TwilioHandler)
#@UsePermission(TwilioPermission)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(SMS_INCOMING_PREFIX )
class IncomingSMSRessource(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self,smsService:SMSService,contactsService:ContactsService,chatService:ChatService) -> None:
        self.smsService: SMSService = smsService
        self.contactsService: ContactsService = contactsService
        self.chatService: ChatService = chatService
        super().__init__(dependencies=[Depends(verify_twilio_token)])

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