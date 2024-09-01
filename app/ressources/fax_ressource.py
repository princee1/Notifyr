from definition._ressource import Ressource
from container import InjectInMethod, InjectInFunction


class IngoingFaxRessource(Ressource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__("fax-ingoing")
    pass

class OutgoingFaxRessource(Ressource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__("fax-ongoing")
    pass