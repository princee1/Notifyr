from datetime import datetime, timezone
from typing import Annotated
from fastapi import BackgroundTasks, Depends, HTTPException, Request, Response
from app.classes.auth_permission import Role
from app.classes.celery import TaskHeaviness, s
from app.classes.stream_data_parser import StreamContinuousDataParser, StreamSequentialDataParser
from app.classes.template import PhoneTemplate
from app.decorators.guards import CeleryTaskGuard, RegisteredContactsGuard, TrackGuard
from app.decorators.handlers import AsyncIOHandler, CeleryTaskHandler, ContactsHandler, CostHandler, ReactiveHandler, ServiceAvailabilityHandler, StreamDataParserHandler, TemplateHandler, TwilioHandler
from app.decorators.interceptors import KeepAliveResponseInterceptor
from app.decorators.permissions import TaskCostPermission, JWTAssetPermission, JWTRouteHTTPPermission, TwilioPermission
from app.decorators.pipes import CeleryTaskPipe, ContactToInfoPipe, ContentIndexPipe, FilterAllowedSchemaPipe, MiniServiceInjectorPipe, OffloadedTaskResponsePipe, TemplateParamsPipe, TemplateValidationInjectionPipe, TwilioPhoneNumberPipe, TwilioResponseStatusPipe, RegisterSchedulerPipe, to_otp_path, force_task_manager_attributes_pipe
from app.models.contacts_model import ContactORM
from app.models.otp_model import GatherDtmfOTPModel, GatherSpeechOTPModel, OTPModel
from app.models.call_model import BaseVoiceCallModel, CallCustomSchedulerModel, CallStatusModel, CallTemplateSchedulerModel, CallTwimlSchedulerModel, GatherResultModel, OnGoingTwimlVoiceCallModel, OnGoingCustomVoiceCallModel
from app.models.twilio_model import CallEventORM, CallStatusEnum
from app.services.assets_service import AssetService
from app.services.profile_service import ProfileService
from app.services.task_service import TaskManager, TaskService, CeleryService, OffloadTaskService
from app.services.chat_service import ChatService
from app.services.contacts_service import ContactsService
from app.services.database_service import RedisService
from app.services.logger_service import LoggerService
from app.services.reactive_service import ReactiveService, ReactiveSubject
from app.services.twilio_service import CallService, TwilioAccountMiniService, TwilioService
from app.definition._ressource import BaseHTTPRessource, BaseHTTPRessource, HTTPMethod, HTTPRessource, IncludeRessource, PingService, UseInterceptor, UseServiceLock, UseGuard, UseHandler, UseLimiter, UsePermission, UsePipe, UseRoles
from app.container import Get, InjectInMethod
from app.depends.dependencies import get_auth_permission, get_request_id
from app.depends.funcs_dep import get_client,Get_Contact, get_task, get_template, verify_twilio_token, background_query, populate_response_with_request_id,wait_timeout_query,get_profile
from app.depends.class_dep import Broker, KeepAliveQuery, SubjectParams, TwilioTracker
from app.utils.constant import StreamConstant
from app.utils.helper import uuid_v1_mc
from app.depends.variables import profile_query

CALL_ONGOING_PREFIX = 'ongoing'
get_contacts = Get_Contact(False,False)


@UseHandler(ServiceAvailabilityHandler, TwilioHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(CALL_ONGOING_PREFIX)
class OnGoingCallRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self, callService: CallService, chatService: ChatService, contactsService: ContactsService) -> None:
        self.callService = callService
        self.chatService = chatService
        self.contactsService = contactsService
        self.offloadTaskService: OffloadTaskService = Get(OffloadTaskService)
        self.reactiveService: ReactiveService = Get(ReactiveService)
        self.redisService:RedisService = Get(RedisService)

        super().__init__()

    @UseLimiter(limit_value="10/minutes")
    @UseRoles([Role.PUBLIC])
    @UsePermission(JWTAssetPermission('sms','xml',accept_none_template=True))
    @UsePipe(FilterAllowedSchemaPipe,before=False)
    @UsePipe(TemplateParamsPipe('phone','xml',True))
    @UseHandler(AsyncIOHandler,TemplateHandler)
    @UseServiceLock(AssetService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/template/{template:path}',methods=[HTTPMethod.OPTIONS])
    def get_template_schema(self,request:Request,response:Response,authPermission=Depends(get_auth_permission),template:str='',wait_timeout: int | float = Depends(wait_timeout_query)):
        
        schemas = self.assetService.get_schema('phone')
        if template in schemas:
            return schemas[template]
        return schemas

    @UseLimiter(limit_value='100/day')
    @UseRoles([Role.MFA_OTP])
    @UsePermission(TaskCostPermission())
    @PingService([ProfileService,TwilioService,CallService],is_manager=True)
    @UseServiceLock(AssetService,lockType='reader')
    @UseServiceLock(ProfileService,TwilioService,lockType='reader',check_status=False)
    @UseHandler(AsyncIOHandler,TemplateHandler,CostHandler)
    @UsePipe(OffloadedTaskResponsePipe(),before=False)
    @UsePipe(MiniServiceInjectorPipe(TwilioService,'twilio','main'),to_otp_path,force_task_manager_attributes_pipe,TwilioPhoneNumberPipe('otp',True), TemplateParamsPipe('phone', 'xml'),TemplateValidationInjectionPipe('phone','','',False))
    @BaseHTTPRessource.Post('/otp/{template:path}',dependencies=[Depends(populate_response_with_request_id)])
    async def voice_relay_otp(self,twilio:Annotated[TwilioAccountMiniService,Depends(profile_query)], template: Annotated[PhoneTemplate,Depends(get_template)], otpModel: OTPModel, request: Request,taskManager: Annotated[TaskManager, Depends(get_task)],profile:str=Depends(profile_query), wait_timeout: int | float = Depends(wait_timeout_query),authPermission=Depends(get_auth_permission)):
        
        _, body = template.build(otpModel.content, ...,True)
        taskManager.set_algorithm('route')
        await taskManager.offload_task(1,0,None,self.callService.send_otp_voice_call,body, otpModel,twilio.miniService_id,_s=s(TaskHeaviness.LIGHT))

        return taskManager.results

    @UsePermission(TaskCostPermission())
    @PingService([ProfileService,TwilioService,CallService],is_manager=True)
    @UseServiceLock(AssetService,lockType='reader')
    @UseServiceLock(ProfileService,TwilioService,lockType='reader',check_status=False)
    @UseLimiter(limit_value='100/day')
    @UseRoles([Role.MFA_OTP])
    @UsePipe(TwilioPhoneNumberPipe('otp',True),)
    @UseInterceptor(KeepAliveResponseInterceptor)
    @UseHandler(CostHandler,AsyncIOHandler,ReactiveHandler,StreamDataParserHandler)
    @BaseHTTPRessource.Get('/otp/', dependencies=[Depends(populate_response_with_request_id)])
    async def enter_digit_otp(self, twilio:Annotated[TwilioAccountMiniService,Depends(profile_query)],otpModel: GatherDtmfOTPModel, request: Request, response: Response, keepAliveConn: Annotated[KeepAliveQuery, Depends(KeepAliveQuery)],profile:str=Depends(profile_query), authPermission=Depends(get_auth_permission)):

        rx_id = keepAliveConn.create_subject('HTTP')
        keepAliveConn.register_lock()
        keepAliveConn.set_stream_parser(StreamSequentialDataParser(['completed','dtmf-result']))
        
        result = self.callService.gather_dtmf(otpModel, rx_id, keepAliveConn.x_request_id)
        call_details = otpModel.model_dump(exclude={'otp', 'content','service','instruction'})
        call_results = await self.callService.send_template_voice_call(result, call_details,subject_id=keepAliveConn.rx_subject.subject_id,twilio_tracking=None,twilio_profile=twilio.miniService_id)

        return await keepAliveConn.wait_for(call_results, 'otp_result')
      

    @UseLimiter(limit_value='100/day')
    @UseRoles([Role.RELAY])
    @UsePermission(TaskCostPermission(),JWTAssetPermission('phone'))
    @PingService([CeleryService,ProfileService,TwilioService,TaskService,CallService],is_manager=True)
    @UseServiceLock(AssetService,lockType='reader')
    @UseServiceLock(ProfileService,TwilioService,lockType='reader',check_status=False)
    @UseHandler(TemplateHandler, CeleryTaskHandler,ContactsHandler,CostHandler)
    @UsePipe(OffloadedTaskResponsePipe(), before=False)
    @UsePipe(MiniServiceInjectorPipe(TwilioService,'twilio','main'),CeleryTaskPipe,RegisterSchedulerPipe,TemplateParamsPipe('phone', 'xml'),ContentIndexPipe(),TemplateValidationInjectionPipe('phone','data','index',True),ContactToInfoPipe('phone','to'), TwilioPhoneNumberPipe('default'))
    @UseGuard(CeleryTaskGuard(['task_send_template_voice_call']),TrackGuard)
    @BaseHTTPRessource.HTTPRoute('/template/{profile}/{template:path}/', methods=[HTTPMethod.POST], dependencies=[Depends(populate_response_with_request_id)])
    async def voice_template(self,profile:str,twilio:Annotated[TwilioAccountMiniService,Depends(get_profile)], template: Annotated[PhoneTemplate,Depends(get_template)], scheduler: CallTemplateSchedulerModel, request: Request, response: Response,broker:Annotated[Broker,Depends(Broker)],tracker:Annotated[TwilioTracker,Depends(TwilioTracker)] ,taskManager: Annotated[TaskManager, Depends(get_task)],wait_timeout: int | float = Depends(wait_timeout_query), authPermission=Depends(get_auth_permission)):
        
        for content in scheduler.content:
            index= content.index
            weight = len(content.to)
            content = content.model_dump(exclude=('as_contact','index','will_track','sender_type'))
            _, result = template.build(content, ...,False)
            twilio_ids = []

            if tracker.will_track:
                for tid,event,tracking_event_data in tracker.pipe_call_track_event_data(content):
                    broker.stream(StreamConstant.TWILIO_TRACKING_CALL,tracking_event_data)
                    broker.stream(StreamConstant.TWILIO_EVENT_STREAM_CALL,event)
                    twilio_ids.append(tid)

            await taskManager.offload_task(weight,0, index, self.callService.send_template_voice_call, result, content,None,twilio_ids,twilio.miniService_id)
        return taskManager.results

    @PingService([CeleryService,ProfileService,TwilioService,TaskService,CallService],is_manager=True)
    @UseServiceLock(ProfileService,TwilioService,lockType='reader',check_status=False)
    @UseLimiter(limit_value='50/day')
    @UseRoles([Role.RELAY])
    @UsePermission(TaskCostPermission())
    @UsePipe(MiniServiceInjectorPipe(TwilioService,'twilio','main'),CeleryTaskPipe,ContentIndexPipe(),ContactToInfoPipe('phone','to'),TwilioPhoneNumberPipe('default'))
    @UseGuard(CeleryTaskGuard(['task_send_twiml_voice_call']),TrackGuard)
    @UseHandler(CeleryTaskHandler,ContactsHandler,CostHandler)
    @UsePipe(OffloadedTaskResponsePipe(), before=False)
    @BaseHTTPRessource.HTTPRoute('/twiml/', methods=[HTTPMethod.POST], dependencies=[Depends(populate_response_with_request_id)], mount=False)
    async def voice_twilio_twiml(self, scheduler: CallTwimlSchedulerModel,twilio:Annotated[TwilioAccountMiniService,Depends(profile_query)], request: Request, response: Response,broker:Annotated[Broker,Depends(Broker)],tracker:Annotated[TwilioTracker,Depends(TwilioTracker)], taskManager: Annotated[TaskManager, Depends(get_task)],profile:str=Depends(profile_query), authPermission=Depends(get_auth_permission)):

        for content in scheduler.content:
            
            weight = len(content.to)
            details = content.model_dump(exclude={'url','as_contact','index','will_track','sender_type'})
            url = content.url
            twilio_ids = []

            if tracker.will_track:
                for tid,event,tracking_event_data in tracker.pipe_call_track_event_data(content):
                    broker.stream(StreamConstant.TWILIO_TRACKING_CALL,tracking_event_data)
                    broker.stream(StreamConstant.TWILIO_EVENT_STREAM_CALL,event)
                    twilio_ids.append(tid)

            await taskManager.offload_task(weight, 0, content.index, self.callService.send_twiml_voice_call, url, details,twilio_tracking_id = twilio_ids,twilio_profile=twilio.miniService_id)
        return taskManager.results

    @PingService([CeleryService,ProfileService,TwilioService,TaskService,CallService],is_manager=True)
    @UseServiceLock(ProfileService,TwilioService,lockType='reader',check_status=False)
    @UseLimiter(limit_value='50/day')
    @UseRoles([Role.RELAY])
    @UsePermission(TaskCostPermission())
    @UsePipe(MiniServiceInjectorPipe(TwilioService,'twilio','main'),CeleryTaskPipe,ContentIndexPipe(),ContactToInfoPipe('phone','to'),TwilioPhoneNumberPipe('default'))
    @UseGuard(CeleryTaskGuard(['task_send_custom_voice_call']),TrackGuard)
    @UseHandler(CeleryTaskHandler,ContactsHandler,CostHandler)
    @UsePipe(OffloadedTaskResponsePipe(), before=False)
    @BaseHTTPRessource.HTTPRoute('/custom/{profile}/', methods=[HTTPMethod.POST], dependencies=[Depends(populate_response_with_request_id)])
    async def voice_custom(self,profile:str,twilio:Annotated[TwilioAccountMiniService,Depends(get_profile)], scheduler: CallCustomSchedulerModel, request: Request, response: Response, broker:Annotated[Broker,Depends(Broker)],tracker:Annotated[TwilioTracker,Depends(TwilioTracker)],taskManager: Annotated[TaskManager, Depends(get_task)], authPermission=Depends(get_auth_permission)):
        for content in scheduler.content:
            details = content.model_dump(
                exclude={'body', 'voice', 'language', 'loop','as_contact','index','will_track','sender_type'})
            body = content.body
            voice = content.voice
            lang = content.language
            loop = content.loop
            twilio_id = []
            weight = len(content.to)


            if tracker.will_track:
                for tid,event,tracking_event_data in tracker.pipe_call_track_event_data(scheduler.content):
                    broker.stream(StreamConstant.TWILIO_TRACKING_CALL,tracking_event_data)
                    broker.stream(StreamConstant.TWILIO_EVENT_STREAM_CALL,event)

                    twilio_id.append(tid)

            await taskManager.offload_task(weight,0, content.index, self.callService.send_custom_voice_call, body, voice, lang, loop, details,twilio_tracking_id = twilio_id,twilio_profile=twilio.miniService_id)
        return taskManager.results

    @PingService([ProfileService,TwilioService,CallService],is_manager=True)
    @UseServiceLock(AssetService,lockType='reader')
    @UseServiceLock(ProfileService,TwilioService,lockType='reader',check_status=False,as_manager=True)
    @UseLimiter(limit_value='50/day')
    @UseRoles([Role.MFA_OTP])
    @UseGuard(RegisteredContactsGuard)
    @UsePipe(MiniServiceInjectorPipe(TwilioService,'twilio','main'),TwilioPhoneNumberPipe('default'))
    @UseInterceptor(KeepAliveResponseInterceptor)
    @UsePermission(TaskCostPermission())
    @UseHandler(AsyncIOHandler,ReactiveHandler,StreamDataParserHandler,CostHandler)
    @BaseHTTPRessource.HTTPRoute('/authenticate/', methods=[HTTPMethod.GET], dependencies=[Depends(populate_response_with_request_id)],mount=False)
    async def voice_authenticate(self, request: Request,twilio:Annotated[TwilioAccountMiniService,Depends(profile_query)], otpModel:GatherSpeechOTPModel, response: Response, contact: Annotated[ContactORM, Depends(get_contacts)], keepAliveConn: Annotated[KeepAliveQuery, Depends(KeepAliveQuery)],profile:str=Depends(profile_query), authPermission=Depends(get_auth_permission)):

        if contact.phone != otpModel.to:
            raise HTTPException(status_code=400,detail='Contact phone number mismatch')
            
        rx_id = keepAliveConn.create_subject('HTTP')
        keepAliveConn.register_lock()
        keepAliveConn.set_stream_parser(StreamContinuousDataParser(['phrase-result','voice-result']))

        call_details = otpModel.model_dump(exclude={'otp', 'content','service','instruction'})

        call_details['record'] = True
        
        result = self.callService.gather_speech(otpModel,rx_id,keepAliveConn.x_request_id)
        call_results = await self.callService.send_template_voice_call(result, call_details,rx_id,twilio_profile=twilio.miniService_id)

        return await keepAliveConn.wait_for(call_results,'otp_result')


CALL_INCOMING_PREFIX = "incoming"


@UseRoles([Role.TWILIO])
@UseHandler(ServiceAvailabilityHandler, TwilioHandler)
# @UsePermission(TwilioPermission)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(CALL_INCOMING_PREFIX)
class IncomingCallRessources(BaseHTTPRessource):
    @InjectInMethod()
    def __init__(self, callService: CallService, chatService: ChatService, contactsService: ContactsService, loggerService: LoggerService,reactiveService:ReactiveService) -> None:
        self.callService = callService
        self.chatService = chatService
        self.contactsService = contactsService
        self.loggerService = loggerService
        self.reactiveService = reactiveService
        self.redisService:RedisService = Get(RedisService)
        # super().__init__(dependencies=[Depends(verify_twilio_token)]) # TODO need to the signature
        super().__init__()

    @BaseHTTPRessource.HTTPRoute('/menu/', methods=[HTTPMethod.POST])
    async def voice_menu(self, authPermission=Depends(get_auth_permission)):
        ...

    @UseRoles([Role.CHAT])
    @BaseHTTPRessource.HTTPRoute('/live-chat/', methods=[HTTPMethod.POST])
    async def voice_live_chat(self, authPermission=Depends(get_auth_permission)):
        pass

    @BaseHTTPRessource.HTTPRoute('/automate-response/', methods=[HTTPMethod.POST])
    async def voice_automate_response(self, authPermission=Depends(get_auth_permission)):
        pass

    @BaseHTTPRessource.HTTPRoute('/handler_fail/', methods=[HTTPMethod.POST])
    async def voice_primary_handler_fail(self, authPermission=Depends(get_auth_permission)):
        pass

    @BaseHTTPRessource.HTTPRoute('/error/', methods=[HTTPMethod.POST])
    async def voice_error(self, authPermission=Depends(get_auth_permission)):
        pass
    
    @UseHandler(ReactiveHandler)
    @UsePipe(TwilioResponseStatusPipe,before=False)
    @BaseHTTPRessource.HTTPRoute('/status/', methods=[HTTPMethod.POST])
    async def voice_call_status(self, status: CallStatusModel, response:Response,broker:Annotated[Broker,Depends(Broker)],subject_params:Annotated[SubjectParams,Depends(SubjectParams)], authPermission=Depends(get_auth_permission),):
        print(status)
        subject_id = subject_params.subject_id
        value = {
                'state':status.CallStatus,
                'data':status.model_dump(include=('CallSid','RecordingSid','Duration','CallDuration','RecordingDuration'))
            }
        broker.publish(StreamConstant.TWILIO_REACTIVE,'plain',subject_id,value,)
        if status.twilio_tracking_id:
            now = datetime.now(timezone.utc).isoformat()
            event = {
                'call_id':status.twilio_tracking_id,
                'call_sid':status.CallSid,
                'date_event_received':now,
                'country':status.ToCountry,
                'city':status.ToCity,
                'state':status.ToState

            }
            if status.CallStatus == 'completed' and (status.Duration == None or status.Duration <=1):
                event['current_event']= CallStatusEnum.DECLINED.value
                event['description'] = f'The callee declined the call'
            else:
                event['current_event']=status.CallStatus.upper(),
                event['description']=f'The call is in the {status.CallStatus} state',
            broker.stream(StreamConstant.TWILIO_EVENT_STREAM_CALL,CallEventORM.JSON(event_id=str(uuid_v1_mc()),direction='O',**event))
        return 

        
    @UseHandler(ReactiveHandler)
    @BaseHTTPRessource.HTTPRoute('/gather-result/', methods=[HTTPMethod.POST])
    async def gather_result(self,gatherResult:GatherResultModel, response:Response,broker:Annotated[Broker,Depends(Broker)],subject_params:Annotated[SubjectParams,Depends(SubjectParams)],authPermission=Depends(get_auth_permission)):
        value =gatherResult.model_dump(include=('data','state'))
        broker.publish(StreamConstant.TWILIO_REACTIVE,'plain',subject_params.subject_id,value,)

        #subject.on_completed()
        return
        
        
    @BaseHTTPRessource.HTTPRoute('/partial-result/', methods=[HTTPMethod.POST])
    async def partial_result(self,authPermission=Depends(get_auth_permission)):
        ...
    


CALL_PREFIX = "call"


@IncludeRessource(IncomingCallRessources, OnGoingCallRessource)
@HTTPRessource(CALL_PREFIX)
class CallRessource(BaseHTTPRessource):

    @UsePermission(JWTRouteHTTPPermission)
    @UseLimiter(limit_value="1/hour")
    @UseRoles([Role.ADMIN])
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.HEAD])
    def weird_head(self, request: Request, response: Response, authPermission=Depends(get_auth_permission)):
        response.status_code = 204
        pass

    