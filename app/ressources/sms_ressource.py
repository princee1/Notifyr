from definition._ressource import AssetRessource
from container import InjectInMethod, InjectInFunction


class OnGoingSMSRessource(AssetRessource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__("sms/ongoing")
    pass


class IncomingSMSRessource(AssetRessource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__("sms/ongoing")
