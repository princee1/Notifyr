from app.definition._ressource import BaseRessource, Ressource
from app.container import InjectInMethod, InjectInFunction


FAX_INCOMING_PREFIX = "fax-incoming"


@Ressource(FAX_INCOMING_PREFIX)
class IncomingFaxRessource(BaseRessource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__()
    

FAX_OUTGOING_PREFIX = "fax_outgoing"
@Ressource(FAX_OUTGOING_PREFIX)
class OutgoingFaxRessource(BaseRessource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__()
    