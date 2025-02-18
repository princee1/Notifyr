from app.classes.auth_permission import Role
from app.decorators.permissions import JWTRouteHTTPPermission
from app.services.chat_service import ChatService
from app.services.contacts_service import ContactsService
from app.services.twilio_service import VoiceService
from app.definition._ressource import BaseHTTPRessource, BaseHTTPRessource, HTTPRessource, UsePermission, UseRoles
from app.container import InjectInMethod, InjectInFunction


CALL_ONGOING_PREFIX = 'call-ongoing'

@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(CALL_ONGOING_PREFIX)
class OnGoingCallRessources(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self, voiceService: VoiceService,contactsService:ContactsService,chatService:ChatService) -> None:
        super().__init__()
        self.voiceService = voiceService
        self.contactsService = contactsService  
        self.chatService = chatService

    @UseRoles([Role.MFA_OTP])
    @BaseHTTPRessource.HTTPRoute('/otp/')
    def voice_relay_otp(self,):
        pass

    @UseRoles([Role.RELAY])
    @BaseHTTPRessource.HTTPRoute('/template/{template}/')
    def voice_template(self,template:str):
        ...


CALL_INCOMING_PREFIX = "call-incoming"


@UseRoles([Role.CHAT])
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(CALL_INCOMING_PREFIX)
class IncomingCallRessources(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self, voiceService: VoiceService,chatService:ChatService) -> None:
        super().__init__()
        self.voiceService = voiceService
        self.chatService = chatService

    @BaseHTTPRessource.HTTPRoute('/call/')
    def voice_relay_otp(self,):
        pass

