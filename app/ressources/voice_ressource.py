from app.services.twilio_service import VoiceService
from app.definition._ressource import BaseHTTPRessource, BaseHTTPRessource, HTTPRessource
from app.container import InjectInMethod, InjectInFunction


CALL_ONGOING_PREFIX = 'call-ongoing'

@HTTPRessource(CALL_ONGOING_PREFIX)
class OnGoingCallRessources(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self, voiceService: VoiceService) -> None:
        super().__init__()
        self.voiceService = voiceService

    def relay_otp(self,):
        pass

    def _add_routes(self):
        return super()._add_routes()


CALL_INCOMING_PREFIX = "call-incoming"
@HTTPRessource(CALL_INCOMING_PREFIX)
class IncomingCallRessources(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self, voiceService: VoiceService) -> None:
        super().__init__()
        self.voiceService = voiceService

    pass
