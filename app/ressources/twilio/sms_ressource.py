from typing import Annotated
from fastapi import Depends, Header, Query, Request, Response
from app.classes.auth_permission import AuthPermission, Role
from app.classes.celery import SchedulerModel, TaskHeaviness, TaskType
from app.classes.template import SMSTemplate
from app.decorators.guards import CarrierTypeGuard, CeleryTaskGuard
from app.decorators.handlers import CeleryTaskHandler, ServiceAvailabilityHandler, TemplateHandler, TwilioHandler
from app.decorators.permissions import JWTAssetPermission,JWTRouteHTTPPermission
from app.decorators.pipes import CeleryTaskPipe, OffloadedTaskResponsePipe, TemplateParamsPipe, TwilioFromPipe, _to_otp_path
from app.definition._ressource import HTTPMethod, HTTPRessource, IncludeRessource, PingService, UseGuard, UseLimiter, UsePermission, BaseHTTPRessource, UseHandler, UsePipe, UseRoles
from app.container import Get, GetDependsFunc, InjectInMethod, InjectInFunction
from app.models.otp_model import OTPModel
from app.models.sms_model import OnGoingBaseSMSModel, OnGoingSMSModel, OnGoingTemplateSMSModel, SMSStatusModel
from app.services.celery_service import TaskManager, TaskService, CeleryService, OffloadTaskService
from app.services.chat_service import ChatService
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.database_service import RedisService
from app.services.twilio_service import SMSService
from app.depends.dependencies import  get_auth_permission, get_query_params, get_request_id
from app.depends.funcs_dep import get_task, verify_twilio_token,populate_response_with_request_id,as_async_query
from app.utils.helper import APIFilterInject



SMS_ONGOING_PREFIX = 'ongoing'



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

    @UseLimiter(limit_value="10/minutes")
    @UseRoles([Role.PUBLIC])
    @UsePipe(TemplateParamsPipe('sms','xml',True))
    @UseHandler(TemplateHandler)
    @BaseHTTPRessource.HTTPRoute('/template/',methods=[HTTPMethod.OPTIONS])
    def get_template_schema(self,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission),template:str=''):
        
        schemas = self.assetService.get_schema('sms')
        if template and template in schemas:
            return schemas[template]
        return schemas


    @UseLimiter(limit_value="10000/minutes")
    @UseRoles([Role.MFA_OTP])
    @UsePipe(_to_otp_path)
    @UsePipe(TwilioFromPipe('TWILIO_OTP_NUMBER'),TemplateParamsPipe('sms','xml'))
    @UseHandler(TemplateHandler)
    @UsePermission(JWTAssetPermission('sms'))
    @UseGuard(CarrierTypeGuard(False,accept_unknown=True))
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
    @UsePipe(OffloadedTaskResponsePipe(),before=False)
    @UseGuard(CarrierTypeGuard(False,accept_unknown=True))
    @UseGuard(CeleryTaskGuard(task_names=['task_send_custom_sms']))
    @BaseHTTPRessource.HTTPRoute('/custom/',methods=[HTTPMethod.POST],dependencies=[Depends(populate_response_with_request_id)])
    async def sms_simple_message(self,scheduler: SMSCustomSchedulerModel,request:Request,response:Response,taskManager:Annotated[TaskManager,Depends(get_task)],authPermission=Depends(get_auth_permission),):
        message = scheduler.content.model_dump()
        await taskManager.offload_task('normal',scheduler,0,None,self.smsService.send_custom_sms,message)
        return taskManager.results
        
    @UseLimiter(limit_value="5000/minutes")
    @UseRoles([Role.RELAY])
    @UseHandler(CeleryTaskHandler,TemplateHandler)
    @UsePipe(TemplateParamsPipe('sms','xml'),CeleryTaskPipe,TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @UsePipe(OffloadedTaskResponsePipe(),before=False)
    @UsePermission(JWTAssetPermission('sms'))
    @UseGuard(CarrierTypeGuard(False,accept_unknown=True))
    @UseGuard(CeleryTaskGuard(['task_send_template_sms']))
    @BaseHTTPRessource.HTTPRoute('/template/{template}',methods=[HTTPMethod.POST],dependencies=[Depends(populate_response_with_request_id)])
    async def sms_template(self,template:str,scheduler: SMSTemplateSchedulerModel,request:Request,response:Response,taskManager:Annotated[TaskManager,Depends(get_task)],authPermission=Depends(get_auth_permission)):
        sms_data = scheduler.content
        smsTemplate:SMSTemplate = self.assetService.sms[template]
        _,result=smsTemplate.build(self.configService.ASSET_LANG,sms_data.data)
        message = {'body':result,'to':sms_data.to,'from_':sms_data.from_}
        await taskManager.offload_task('normal',scheduler,0,None,self.smsService.send_template_sms,message)
        return taskManager.results


    async def sms_get_message(self,):
        ...

    async def sms_delete_message(self,):
        ...



SMS_INCOMING_PREFIX = "incoming"

@UseRoles([Role.TWILIO])
@PingService([SMSService])
@UseHandler(ServiceAvailabilityHandler,TwilioHandler)
#@UsePermission(TwilioPermission)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(SMS_INCOMING_PREFIX )
class IncomingSMSRessource(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self,smsService:SMSService,contactsService:ContactsService,chatService:ChatService,redisService:RedisService) -> None:
        self.smsService: SMSService = smsService
        self.contactsService: ContactsService = contactsService
        self.chatService: ChatService = chatService
        self.redisService:RedisService = redisService
        #super().__init__(dependencies=[Depends(verify_twilio_token)])
        super().__init__()

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

        

SMS_PREFIX = "sms"
@IncludeRessource(IncomingSMSRessource,OnGoingSMSRessource)
@HTTPRessource(SMS_PREFIX)
class SMSRessource(BaseHTTPRessource):

    @UsePermission(JWTRouteHTTPPermission)
    @UseLimiter(limit_value="1/hour")
    @UseRoles([Role.ADMIN])
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.HEAD])
    def weird_head(self,request:Request,response:Response,authPermission=Depends(get_auth_permission)):
        response.status_code = 204
        return