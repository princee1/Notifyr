from app.definition._ressource import BaseRessource, Ressource
from app.container import InjectInMethod, InjectInFunction


SIP_INCOMING_PREFIX = "sip-incoming"
@Ressource(SIP_INCOMING_PREFIX)
class IncomingSipRessource(BaseRessource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__()
    


SIP_ONGOING_PREFIX = "sip_ongoing"
@Ressource(SIP_ONGOING_PREFIX)
class OutgoingSipRessource(BaseRessource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__()
    