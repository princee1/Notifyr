import asyncio
from typing import Annotated, Any
from fastapi import Depends, HTTPException, Request, Response
from app.classes.auth_permission import Role
from app.classes.celery import SchedulerModel, TaskHeaviness, TaskType
from app.classes.template import PhoneTemplate
from app.decorators.guards import CeleryTaskGuard, RegisteredContactsGuard
from app.decorators.handlers import AsyncIOHandler, CeleryTaskHandler, ServiceAvailabilityHandler, TemplateHandler, TwilioHandler
from app.decorators.permissions import JWTAssetPermission, JWTRouteHTTPPermission, TwilioPermission
from app.decorators.pipes import CeleryTaskPipe, KeepAliveResponsePipe, OffloadedTaskResponsePipe, TemplateParamsPipe, TwilioFromPipe, _to_otp_path
from app.models.otp_model import GatherDtmfOTPModel, OTPModel
from app.models.security_model import ClientORM
from app.models.voice_model import BaseVoiceCallModel, CallStatusModel, OnGoingTwimlVoiceCallModel, OnGoingCustomVoiceCallModel
from app.services.celery_service import TaskManager, TaskService, CeleryService, OffloadTaskService
from app.services.chat_service import ChatService
from app.services.contacts_service import ContactsService
from app.services.logger_service import LoggerService
from app.services.reactive_service import ReactiveService
from app.services.twilio_service import CallService
from app.definition._ressource import BaseHTTPRessource, BaseHTTPRessource, HTTPMethod, HTTPRessource, IncludeRessource, PingService, UseGuard, UseHandler, UseLimiter, UsePermission, UsePipe, UseRoles
from app.container import Get, InjectInMethod
from app.depends.dependencies import get_auth_permission, get_request_id
from app.depends.my_depends import KeepAliveQuery, get_client, get_task, verify_twilio_token, as_async_query, populate_response_with_request_id


CALL_ONGOING_PREFIX = 'ongoing'


class CallTemplateSchedulerModel(SchedulerModel):
    content: BaseVoiceCallModel


class CallTwimlSchedulerModel(SchedulerModel):
    content: OnGoingTwimlVoiceCallModel


class CallCustomSchedulerModel(SchedulerModel):
    content: OnGoingCustomVoiceCallModel


@PingService([CallService])
@UseHandler(ServiceAvailabilityHandler, TwilioHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(CALL_ONGOING_PREFIX)
class OnGoingCallRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self, callService: CallService, chatService: ChatService, contactsService: ContactsService) -> None:
        self.callService = callService
        self.chatService = chatService
        self.contactsService = contactsService
        self.offloadTaskService: OffloadTaskService = Get(OffloadTaskService)
        self.reactiveService: ReactiveService = Get(ReactiveService)
        super().__init__()

    @UseLimiter(limit_value="10/minutes")
    @UseRoles([Role.PUBLIC])
    @UsePipe(TemplateParamsPipe('phone','xml',True))
    @UseHandler(TemplateHandler)
    @BaseHTTPRessource.HTTPRoute('/template/',methods=[HTTPMethod.OPTIONS])
    def get_template_schema(self,request:Request,response:Response,authPermission=Depends(get_auth_permission),template:str=''):
        
        schemas = self.assetService.get_schema('phone')
        if template in schemas:
            return schemas[template]
        return schemas

    @UseLimiter(limit_value='100/day')
    @UseRoles([Role.MFA_OTP])
    @UseHandler(TemplateHandler)
    @UsePipe(_to_otp_path)
    @UsePipe(TwilioFromPipe('TWILIO_OTP_NUMBER'), TemplateParamsPipe('phone', 'xml'))
    @BaseHTTPRessource.Post('/otp/{template}')
    def voice_relay_otp(self, template: str, otpModel: OTPModel, request: Request, authPermission=Depends(get_auth_permission)):
        phoneTemplate: PhoneTemplate = self.assetService.phone[template]
        _, body = phoneTemplate.build(otpModel.content, ...)
        return self.callService.send_otp_voice_call(body, otpModel)

    @UseLimiter(limit_value='100/day')
    @UseRoles([Role.MFA_OTP])
    @UsePipe(TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @UsePipe(KeepAliveResponsePipe, before=False)
    @UseHandler(AsyncIOHandler)
    @BaseHTTPRessource.Get('/otp/', dependencies=[Depends(populate_response_with_request_id)])
    async def enter_digit_otp(self, otpModel: GatherDtmfOTPModel, request: Request, response: Response, keepAliveConn: Annotated[KeepAliveQuery, Depends(KeepAliveQuery)], authPermission=Depends(get_auth_permission)):
        if not otpModel.otp:
            raise HTTPException(status_code=400, detail="OTP is required")

        rx_id = keepAliveConn.create_subject('HTTP')
        keepAliveConn.register_lock()
        
        result = self.callService.gather_dtmf(otpModel, rx_id, keepAliveConn.x_request_id)
        call_details = otpModel.model_dump(exclude={'otp', 'content','service'})
        call_results = self.callService.send_template_voice_call(result, call_details)

        return await keepAliveConn.wait_for(call_results, 'verified')
   

    @UseLimiter(limit_value='100/day')
    @UseRoles([Role.RELAY])
    @UsePermission(JWTAssetPermission('phone'))
    @UseHandler(TemplateHandler, CeleryTaskHandler)
    @UsePipe(OffloadedTaskResponsePipe, before=False)
    @UsePipe(TemplateParamsPipe('phone', 'xml'), CeleryTaskPipe, TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @UseGuard(CeleryTaskGuard(['task_send_template_voice_call']))
    @BaseHTTPRessource.HTTPRoute('/template/{template}/', methods=[HTTPMethod.POST], dependencies=[Depends(populate_response_with_request_id)])
    async def voice_template(self, template: str, scheduler: CallTemplateSchedulerModel, request: Request, response: Response, taskManager: Annotated[TaskManager, Depends(get_task)], authPermission=Depends(get_auth_permission)):
        content = scheduler.content.model_dump()
        phoneTemplate: PhoneTemplate = self.assetService.phone[template]
        _, result = phoneTemplate.build(content, ...)
        await taskManager.offload_task('normal', scheduler, 0, None, self.callService.send_template_voice_call, result, content)
        return taskManager.results

    @UseLimiter(limit_value='50/day')
    @UseRoles([Role.RELAY])
    @UsePipe(CeleryTaskPipe, TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @UseGuard(CeleryTaskGuard(['task_send_twiml_voice_call']))
    @UseHandler(CeleryTaskHandler)
    @UsePipe(OffloadedTaskResponsePipe, before=False)
    @BaseHTTPRessource.HTTPRoute('/twiml/', methods=[HTTPMethod.POST], dependencies=[Depends(populate_response_with_request_id)], mount=False)
    async def voice_twilio_twiml(self, scheduler: CallTwimlSchedulerModel, request: Request, response: Response, taskManager: Annotated[TaskManager, Depends(get_task)], authPermission=Depends(get_auth_permission)):
        details = scheduler.content.model_dump(exclude={'url'})
        url = scheduler.content.url
        await taskManager.offload_task('normal', scheduler, 0, None, self.callService.send_twiml_voice_call, url, details)
        return taskManager.results

    @UseLimiter(limit_value='50/day')
    @UseRoles([Role.RELAY])
    @UsePipe(CeleryTaskPipe, TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @UseGuard(CeleryTaskGuard(['task_send_custom_voice_call']))
    @UseHandler(CeleryTaskHandler)
    @UsePipe(OffloadedTaskResponsePipe, before=False)
    @BaseHTTPRessource.HTTPRoute('/custom/', methods=[HTTPMethod.POST], dependencies=[Depends(populate_response_with_request_id)])
    async def voice_custom(self, scheduler: CallCustomSchedulerModel, request: Request, response: Response, taskManager: Annotated[TaskManager, Depends(get_task)], authPermission=Depends(get_auth_permission)):
        details = scheduler.content.model_dump(
            exclude={'body', 'voice', 'language', 'loop'})
        body = scheduler.content.body
        voice = scheduler.content.voice
        lang = scheduler.content.language
        loop = scheduler.content.loop
        await taskManager.offload_task('normal', scheduler, 0, None, self.callService.send_custom_voice_call, body, voice, lang, loop, details)

    @UseLimiter(limit_value='50/day')
    @UseRoles([Role.MFA_OTP])
    @UseGuard(RegisteredContactsGuard)
    @UsePipe(TwilioFromPipe('TWILIO_OTP_NUMBER'))
    @UsePipe(KeepAliveResponsePipe, before=False)
    @UseHandler(AsyncIOHandler)
    @BaseHTTPRessource.HTTPRoute('/authenticate/', methods=[HTTPMethod.GET], dependencies=[Depends(populate_response_with_request_id)],mount=False)
    async def voice_authenticate(self, request: Request, response: Response, client: Annotated[ClientORM, Depends(get_client)], keepAliveConn: Annotated[KeepAliveQuery, Depends(KeepAliveQuery)], authPermission=Depends(get_auth_permission)):

        rx_id = keepAliveConn.create_subject('HTTP')
        keepAliveConn.register_lock()

        result = self.callService.gather_speech(rx_id)
        call_results = self.callService.send_template_voice_call(result, {})

        return await keepAliveConn.wait_for(call_results,'verified')


CALL_INCOMING_PREFIX = "incoming"


@UseRoles([Role.TWILIO])
@PingService([CallService])
@UseHandler(ServiceAvailabilityHandler, TwilioHandler)
# @UsePermission(TwilioPermission)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(CALL_INCOMING_PREFIX)
class IncomingCallRessources(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self, callService: CallService, chatService: ChatService, contactsService: ContactsService, loggerService: LoggerService) -> None:
        self.callService = callService
        self.chatService = chatService
        self.contactsService = contactsService
        self.loggerService = loggerService
        super().__init__(dependencies=[Depends(verify_twilio_token)])

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

    @BaseHTTPRessource.HTTPRoute('/status/', methods=[HTTPMethod.POST])
    async def voice_call_status(self, status: CallStatusModel, authPermission=Depends(get_auth_permission)):
        ...

    @BaseHTTPRessource.HTTPRoute('/error/', methods=[HTTPMethod.POST])
    async def voice_error(self, authPermission=Depends(get_auth_permission)):
        pass


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

    