from services.twilio_service import VoiceService
from definition._ressource import AssetRessource, Ressource
from container import InjectInMethod, InjectInFunction


class OnGoingCallRessources(Ressource):
    @InjectInMethod
    def __init__(self,voiceService: VoiceService) -> None:
        super().__init__("call/ongoing")
        self.voiceService = voiceService
    pass


class IncomingCallRessources(Ressource):
    @InjectInMethod
    def __init__(self,voiceService: VoiceService) -> None:
        super().__init__("call/incoming")
        self.voiceService = voiceService

    pass
