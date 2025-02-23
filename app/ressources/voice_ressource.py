from typing import Any
from fastapi import Depends
from app.classes.auth_permission import Role
from app.classes.celery import SchedulerModel
from app.decorators.guards import CeleryTaskGuard, RegisteredContactsGuard
from app.decorators.handlers import CeleryTaskHandler, ServiceAvailabilityHandler, TemplateHandler, TwilioHandler
from app.decorators.permissions import JWTAssetPermission, JWTRouteHTTPPermission
from app.decorators.pipes import CeleryTaskPipe, TemplateParamsPipe
from app.models.otp_model import OTPModel
from app.services.celery_service import CeleryService
from app.services.chat_service import ChatService
from app.services.contacts_service import ContactsService
from app.services.logger_service import LoggerService
from app.services.twilio_service import VoiceService
from app.definition._ressource import BaseHTTPRessource, BaseHTTPRessource, HTTPRessource, PingService, UseGuard, UseHandler, UsePermission, UsePipe, UseRoles
from app.container import Get, InjectInMethod, InjectInFunction
from app.utils.dependencies import get_auth_permission


CALL_ONGOING_PREFIX = 'call-ongoing'

class VoiceSchedulerModel(SchedulerModel):
    content: Any # TODO

@PingService([VoiceService])
@UseHandler(ServiceAvailabilityHandler,TwilioHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(CALL_ONGOING_PREFIX)
class OnGoingCallRessources(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self, voiceService: VoiceService,chatService:ChatService,contactsService:ContactsService) -> None:
        self.voiceService = voiceService
        self.chatService = chatService
        self.contactsService = contactsService
        self.celeryService: CeleryService = Get(CeleryService)

        super().__init__()


    @UseRoles([Role.MFA_OTP])
    @BaseHTTPRessource.HTTPRoute('/otp/',methods=['POST'])
    def voice_relay_otp(self,otpModel:OTPModel,authPermission=Depends(get_auth_permission)):
        pass
    
    @UsePermission(JWTAssetPermission('phone'))
    @UseHandler(TemplateHandler,CeleryTaskHandler)
    @UsePipe(TemplateParamsPipe('phone'),CeleryTaskPipe)
    @UseGuard(CeleryTaskGuard(['']))
    @UseRoles([Role.RELAY])
    @BaseHTTPRessource.HTTPRoute('/template/{template}/',methods=['POST'])
    def voice_template(self,template:str,scheduler: VoiceSchedulerModel,authPermission=Depends(get_auth_permission)):
        ...

    @UseRoles([Role.RELAY])
    @UsePipe(CeleryTaskPipe)
    @UseGuard(CeleryTaskGuard(['']))
    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.HTTPRoute('/custom',methods=['POST'])
    def voice_custom(self,scheduler: VoiceSchedulerModel,authPermission=Depends(get_auth_permission)):
        ...
    
    @UseRoles([Role.MFA_OTP])
    @UseGuard(RegisteredContactsGuard)
    @BaseHTTPRessource.HTTPRoute('/authenticate/',methods=['GET'])
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


    @BaseHTTPRessource.HTTPRoute('/menu/')
    async def voice_menu(self,authPermission=Depends(get_auth_permission)):
        ...
    
    @UseRoles([Role.CHAT])
    @BaseHTTPRessource.HTTPRoute('/live-chat/')
    async def voice_live_chat(self,authPermission=Depends(get_auth_permission)):
        pass

    @BaseHTTPRessource.HTTPRoute('/automate-response/')
    async def voice_automate_response(self,authPermission=Depends(get_auth_permission)):
        pass

    @BaseHTTPRessource.HTTPRoute('/handler_fail/',methods=['POST'])
    async def voice_primary_handler_fail(self,authPermission=Depends(get_auth_permission)):
        pass

    @BaseHTTPRessource.HTTPRoute('/status/',methods=['POST'])
    async def voice_call_status_changes(self,authPermission=Depends(get_auth_permission)):
        ...

    @BaseHTTPRessource.HTTPRoute('/error/',methods=['POST'])
    async def voice_error(self,authPermission=Depends(get_auth_permission)):
        pass