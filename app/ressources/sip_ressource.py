from definition._ressource import Ressource
from container import InjectInMethod, InjectInFunction


SIP_INCOMING_PREFIX = "sip-incoming"
class IncomingSipRessource(Ressource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__("sip-incoming")
    

SIP_ONGOING_PREFIX = "sip_ongoing"
class OutgoingSipRessource(Ressource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__("sip-ongoing")
    