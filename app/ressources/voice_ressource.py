from fastapi import Depends
from app.classes.auth_permission import Role
from app.decorators.guards import ContactsGuard
from app.decorators.handlers import ServiceAvailabilityHandler
from app.decorators.permissions import JWTRouteHTTPPermission
from app.services.chat_service import ChatService
from app.services.contacts_service import ContactsService
from app.services.twilio_service import VoiceService
from app.definition._ressource import BaseHTTPRessource, BaseHTTPRessource, HTTPRessource, PingService, UseGuard, UseHandler, UsePermission, UseRoles
from app.container import InjectInMethod, InjectInFunction


CALL_ONGOING_PREFIX = 'call-ongoing'

@PingService([VoiceService])
@UseHandler(ServiceAvailabilityHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(CALL_ONGOING_PREFIX)
class OnGoingCallRessources(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self, voiceService: VoiceService,chatService:ChatService,contactsService:ContactsService) -> None:
        self.voiceService = voiceService

        super().__init__(dependencies=[Depends(self.voiceService.verify_twilio_token)])
        self.chatService = chatService
        self.contactsService = contactsService

    @UseRoles([Role.MFA_OTP])
    @BaseHTTPRessource.HTTPRoute('/otp/',methods=['POST'])
    def voice_relay_otp(self,):
        pass

    @UseRoles([Role.RELAY])
    @BaseHTTPRessource.HTTPRoute('/template/{template}/',methods=['POST'])
    def voice_template(self,template:str):
        ...

    @BaseHTTPRessource.HTTPRoute('/custom',methods=['POST'])
    def voice_custom(self,):
        ...
    
    @UseRoles([Role.MFA_OTP])
    @UseGuard(ContactsGuard)
    @BaseHTTPRessource.HTTPRoute('/authenticate/',methods=['GET'])
    def voice_authenticate(self):
        ...
    




CALL_INCOMING_PREFIX = "call-incoming"

@UseRoles([Role.CHAT])
@PingService([VoiceService])
@UseHandler(ServiceAvailabilityHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(CALL_INCOMING_PREFIX)
class IncomingCallRessources(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self, voiceService: VoiceService,chatService:ChatService,contactsService:ContactsService) -> None:
        self.voiceService = voiceService
        super().__init__(dependencies=[Depends(self.voiceService.verify_twilio_token)])
        self.chatService = chatService
        self.contactsService = contactsService


    @BaseHTTPRessource.HTTPRoute('/menu/')
    def voice_menu(self):
        ...
    
    @BaseHTTPRessource.HTTPRoute('/live-chat/')
    def voice_live_chat(self,):
        pass


    @BaseHTTPRessource.HTTPRoute('/automate-response/')
    def voice_automate_response(self,):
        pass

