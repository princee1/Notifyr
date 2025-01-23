from app.definition._ressource import BaseHTTPRessource, HTTPRessource
from app.container import InjectInMethod, InjectInFunction


FAX_INCOMING_PREFIX = "fax-incoming"


@HTTPRessource(FAX_INCOMING_PREFIX)
class IncomingFaxRessource(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__()
    

FAX_OUTGOING_PREFIX = "fax_outgoing"
@HTTPRessource(FAX_OUTGOING_PREFIX)
class OutgoingFaxRessource(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__()
    