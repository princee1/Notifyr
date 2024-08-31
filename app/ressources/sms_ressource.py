from definition._ressource import Ressource
from container import InjectInMethod, InjectInFunction


class OnGoingSMSRessource(Ressource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__("sms/ongoing")
    pass


class IncomingSMSRessource(Ressource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__("sms/ongoing")
