from services.twilio_service import VoiceService
from definition._ressource import Ressource, Ressource
from container import InjectInMethod, InjectInFunction


CALL_ONGOING_PREFIX = 'call-ongoing'


class OnGoingCallRessources(Ressource):
    @InjectInMethod
    def __init__(self, voiceService: VoiceService) -> None:
        super().__init__("call-ongoing")
        self.voiceService = voiceService

    def relay_otp(self,):
        pass

    def _add_routes(self):
        return super()._add_routes()


CALL_INCOMING_PREFIX = "call-incoming"
class IncomingCallRessources(Ressource):
    @InjectInMethod
    def __init__(self, voiceService: VoiceService) -> None:
        super().__init__("call-incoming")
        self.voiceService = voiceService

    pass
