from services.twilio_service import VoiceService
from definition._ressource import BaseRessource, BaseRessource, Ressource
from container import InjectInMethod, InjectInFunction


CALL_ONGOING_PREFIX = 'call-ongoing'

@Ressource(CALL_ONGOING_PREFIX)
class OnGoingCallRessources(BaseRessource):
    @InjectInMethod
    def __init__(self, voiceService: VoiceService) -> None:
        super().__init__()
        self.voiceService = voiceService

    def relay_otp(self,):
        pass

    def _add_routes(self):
        return super()._add_routes()


CALL_INCOMING_PREFIX = "call-incoming"
@Ressource(CALL_INCOMING_PREFIX)
class IncomingCallRessources(BaseRessource):
    @InjectInMethod
    def __init__(self, voiceService: VoiceService) -> None:
        super().__init__()
        self.voiceService = voiceService

    pass
