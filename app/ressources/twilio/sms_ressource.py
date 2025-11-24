from datetime import datetime, timezone
from typing import Annotated
from fastapi import Depends, Request, Response
from app.classes.auth_permission import AuthPermission, Role
from app.classes.celery import  TaskHeaviness, s
from app.classes.template import SMSTemplate
from app.cost.sms_cost import SMSCost
from app.decorators.guards import CarrierTypeGuard, CeleryTaskGuard
from app.decorators.handlers import AsyncIOHandler, CeleryTaskHandler, ContactsHandler, CostHandler, MiniServiceHandler, ProfileHandler, ServiceAvailabilityHandler, TemplateHandler, TwilioHandler
from app.decorators.interceptors import TaskCostInterceptor
from app.decorators.permissions import TaskCostPermission, JWTAssetPermission,JWTRouteHTTPPermission
from app.decorators.pipes import CeleryTaskPipe, ContactToInfoPipe, ContentIndexPipe, FilterAllowedSchemaPipe, MiniServiceInjectorPipe, OffloadedTaskResponsePipe, TemplateParamsPipe, TemplateValidationInjectionPipe, TwilioPhoneNumberPipe, RegisterSchedulerPipe, to_otp_path, force_task_manager_attributes_pipe
from app.definition._cost import SimpleTaskCost
from app.definition._ressource import HTTPMethod, HTTPRessource, IncludeRessource, PingService, UseInterceptor, UseServiceLock, UseGuard, UseLimiter, UsePermission, BaseHTTPRessource, UseHandler, UsePipe, UseRoles
from app.container import InjectInMethod
from app.depends.class_dep import  TwilioTracker
from app.manager.broker_manager import Broker
from app.manager.task_manager import TaskManager
from app.models.otp_model import OTPModel
from app.models.sms_model import  SMSCustomSchedulerModel, SMSStatusModel, SMSTemplateSchedulerModel
from app.models.twilio_model import SMSEventORM
from app.services.profile_service import ProfileService
from app.services.setting_service import SettingService
from app.services.task_service import  TaskService, CeleryService
from app.services.assets_service import AssetService
from app.services.chat_service import ChatService
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.database_service import RedisService
from app.services.twilio_service import SMSService, TwilioAccountMiniService, TwilioService
from app.depends.dependencies import  get_auth_permission
from app.depends.variables import profile_query
from app.depends.funcs_dep import get_profile, get_template,wait_timeout_query
from app.utils.constant import CostConstant, SpecialKeyAttributesConstant, StreamConstant
from app.utils.helper import APIFilterInject, uuid_v1_mc



SMS_ONGOING_PREFIX = 'ongoing'

#@PingService([SMSService])
@UseHandler(ServiceAvailabilityHandler,TwilioHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(SMS_ONGOING_PREFIX)
class OnGoingSMSRessource(BaseHTTPRessource):
    @InjectInMethod()
    def __init__(self, smsService: SMSService,chatService:ChatService,contactService:ContactsService,configService:ConfigService,settingService:SettingService,twilioService:TwilioService) -> None:
        super().__init__()
        self.smsService: SMSService = smsService
        self.chatService: ChatService = chatService
        self.contactService: ContactsService = contactService
        self.configService:ConfigService = configService
        self.settingService = settingService
        self.twilioService = twilioService

    @UseLimiter(limit_value="10/minutes")
    @UseRoles([Role.PUBLIC])
    @UsePermission(JWTAssetPermission('sms','xml',accept_none_template=True))
    @UsePipe(FilterAllowedSchemaPipe,before=False)
    @UseServiceLock(AssetService,lockType='reader')
    @UsePipe(TemplateParamsPipe('sms','xml',True))
    @UseHandler(AsyncIOHandler,TemplateHandler)
    @BaseHTTPRessource.HTTPRoute('/template/{template:path}',methods=[HTTPMethod.OPTIONS])
    def get_template_schema(self,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission),template:str='',wait_timeout: int | float = Depends(wait_timeout_query)):

        schemas = self.assetService.get_schema('sms')
        if template and template in schemas:
            return schemas[template]
        return schemas


    @UseLimiter(limit_value="10000/minutes")
    @UseRoles([Role.MFA_OTP])
    @PingService([ProfileService,TwilioService,SMSService],is_manager=True)
    @UseServiceLock(AssetService,lockType='reader')
    @UseServiceLock(ProfileService,TwilioService,as_manager=True,check_status=False)
    @UsePipe(OffloadedTaskResponsePipe(),before=False)
    @UseHandler(MiniServiceHandler,AsyncIOHandler,TemplateHandler,ProfileHandler,CostHandler)
    @UsePermission(TaskCostPermission(),JWTAssetPermission('sms'))
    @UseGuard(CarrierTypeGuard(False,accept_unknown=True))
    @UseInterceptor(TaskCostInterceptor(),inject_meta=True)
    @UsePipe(MiniServiceInjectorPipe(TwilioService,'twilio','main'),to_otp_path,force_task_manager_attributes_pipe,TwilioPhoneNumberPipe('otp',True),TemplateParamsPipe('sms','xml'),TemplateValidationInjectionPipe('sms','','',False))
    @BaseHTTPRessource.HTTPRoute('/otp/{template:path}/',methods=[HTTPMethod.POST],cost_definition=CostConstant.sms_otp)
    async def sms_relay_otp(self,twilio:Annotated[TwilioAccountMiniService,Depends(profile_query)],broker:Annotated[Broker,Depends(Broker)], template:Annotated[SMSTemplate,Depends(get_template)],cost:Annotated[SimpleTaskCost,Depends(SimpleTaskCost)],otpModel:OTPModel,request:Request,response:Response,taskManager: Annotated[TaskManager, Depends(TaskManager)],profile:str=Depends(profile_query),wait_timeout: int | float = Depends(wait_timeout_query),authPermission=Depends(get_auth_permission)):
        
        _,body= template.build(otpModel.content,...,True)
        taskManager.set_algorithm('route')
        await taskManager.offload_task(1,10,None,self.smsService.send_otp,otpModel,body,twilio_profile=twilio.miniService_id,_s=s(TaskHeaviness.LIGHT))
        return taskManager.results
        
    @UsePermission(TaskCostPermission())
    @UseLimiter(limit_value="5000/minutes")
    @UseRoles([Role.RELAY,Role.MFA_OTP])    
    @UseHandler(MiniServiceHandler,CeleryTaskHandler,ContactsHandler,ProfileHandler,CostHandler)
    @UsePipe(MiniServiceInjectorPipe(TwilioService,'twilio','main'),CeleryTaskPipe,ContentIndexPipe(),ContactToInfoPipe('phone','to'),TwilioPhoneNumberPipe('default'))
    @UsePipe(OffloadedTaskResponsePipe(),before=False)
    @UseInterceptor(TaskCostInterceptor(),inject_meta=True)
    @UseServiceLock(ProfileService,TwilioService,as_manager=True,check_status=False,lockType='reader')
    @PingService([CeleryService,ProfileService,TwilioService,TaskService,SMSService],is_manager=True)
    @UseGuard(CarrierTypeGuard(False,accept_unknown=True),CeleryTaskGuard(task_names=['task_send_custom_sms']))
    @BaseHTTPRessource.HTTPRoute('/custom/{profile}/',methods=[HTTPMethod.POST],cost_definition=CostConstant.sms_message)
    async def sms_simple_message(self,profile:str,twilio:Annotated[TwilioAccountMiniService,Depends(get_profile)],scheduler: SMSCustomSchedulerModel,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[SMSCost,Depends(SMSCost)],taskManager:Annotated[TaskManager,Depends(TaskManager)],tracker:Annotated[TwilioTracker,Depends(TwilioTracker)], authPermission=Depends(get_auth_permission),):
        
        for content in scheduler.content:
            message = content.model_dump(exclude=('as_contact','index','will_track','sender_type'))
            twilio_ids = []
            weight = len(content.to)

            if tracker.will_track:
                for tid,event,tracking_event_data in tracker.pipe_sms_track_event_data(content):
                    broker.stream(StreamConstant.TWILIO_TRACKING_SMS,tracking_event_data)
                    broker.stream(StreamConstant.TWILIO_EVENT_STREAM_SMS,event)

                    twilio_ids.append(tid)
            
            await taskManager.offload_task(weight,0,content.index,self.smsService.send_custom_sms,message,twilio_tracking_id = twilio_ids,twilio_profile=twilio.miniService_id)
        return taskManager.results
        
    @UseLimiter(limit_value="5000/minutes")
    @UseRoles([Role.RELAY])
    @PingService([CeleryService,ProfileService,TwilioService,TaskService,SMSService], is_manager=True)
    @UseHandler(MiniServiceHandler,CeleryTaskHandler,TemplateHandler,ContactsHandler,AsyncIOHandler,ProfileHandler,CostHandler)
    @UsePipe(MiniServiceInjectorPipe(TwilioService,'twilio','main'),RegisterSchedulerPipe,TemplateParamsPipe('sms','xml'),ContentIndexPipe(),TemplateValidationInjectionPipe('sms','data','index'),CeleryTaskPipe,ContactToInfoPipe('phone','to'),TwilioPhoneNumberPipe('default'))
    @UsePipe(OffloadedTaskResponsePipe(),before=False)
    @UseInterceptor(TaskCostInterceptor(),inject_meta=True)
    @UsePermission(TaskCostPermission(),JWTAssetPermission('sms'))
    @UseGuard(CarrierTypeGuard(False,accept_unknown=True),CeleryTaskGuard(['task_send_template_sms']))
    @UseServiceLock(AssetService,lockType='reader')
    @UseServiceLock(ProfileService,TwilioService,as_manager=True,check_status=False,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/template/{profile}/{template}',methods=[HTTPMethod.POST],cost_definition=CostConstant.sms_template)
    async def sms_template(self,profile:str,twilio:Annotated[TwilioAccountMiniService,Depends(get_profile)],template: Annotated[SMSTemplate,Depends(get_template)],scheduler: SMSTemplateSchedulerModel,cost:Annotated[SMSCost,Depends(SMSCost)],request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],tracker:Annotated[TwilioTracker,Depends(TwilioTracker)],taskManager:Annotated[TaskManager,Depends(TaskManager)],wait_timeout: int | float = Depends(wait_timeout_query),authPermission=Depends(get_auth_permission)):
        for content in scheduler.content:
            weight = len(content.to)
            _,result=template.build(content.data,self.settingService.ASSET_LANG)
            message = {'body':result,'to':content.to,'from_':content.from_}

            twilio_ids=[]
            if tracker.will_track:
                for tid,event,tracking_event_data in tracker.pipe_sms_track_event_data(content):
                    broker.stream(StreamConstant.TWILIO_TRACKING_SMS,tracking_event_data)
                    broker.stream(StreamConstant.TWILIO_EVENT_STREAM_SMS,event)

                    twilio_ids.append(tid)

            await taskManager.offload_task(weight,0,content.index,self.smsService.send_template_sms,message,twilio_tracking_id=twilio_ids,twilio_profile=twilio.miniService_id)
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
    @InjectInMethod()
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
    async def sms_call_status_changes(self,status: SMSStatusModel,broker:Annotated[Broker,Depends(Broker)], authPermission=Depends(get_auth_permission)):
        print(status)
        if status.twilio_tracking_id:
            event = 'QUEUED' if status.MessageStatus == 'sent' else 'QUEUED'
            now = datetime.now(timezone.utc).isoformat()
            event = {
                'sms_id':status.twilio_tracking_id,
                'sms_sid':status.SmsSid,
                'current_event':event,
                'description':f'The sms is in the {status.MessageStatus} state',
                'date_event_received':now,
            }
            broker.stream(StreamConstant.TWILIO_EVENT_STREAM_SMS,SMSEventORM.JSON(event_id=str(uuid_v1_mc()),direction='O',**event))

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