from app.definition._ressource import BaseHTTPRessource, HTTPRessource
from app.container import InjectInMethod, InjectInFunction


SIP_INCOMING_PREFIX = "sip-incoming"
@HTTPRessource(SIP_INCOMING_PREFIX)
class IncomingSipRessource(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__()
    


SIP_ONGOING_PREFIX = "sip_ongoing"
@HTTPRessource(SIP_ONGOING_PREFIX)
class OutgoingSipRessource(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__()
    