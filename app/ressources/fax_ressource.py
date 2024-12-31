from definition._ressource import Ressource
from container import InjectInMethod, InjectInFunction


FAX_INCOMING_PREFIX = "fax-incoming"
class IncomingFaxRessource(Ressource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__("fax-incoming")
    

FAX_OUTGOING_PREFIX = "fax_outgoing"
class OutgoingFaxRessource(Ressource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__("fax-ongoing")
    