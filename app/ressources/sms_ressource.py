from definition._ressource import AssetRessource
from container import InjectInConstructor, InjectInFunction


class OnGoingSMSRessource(AssetRessource):
    @InjectInConstructor
    def __init__(self,) -> None:
        super().__init__("sms/ongoing")
    pass


class IncomingSMSRessource(AssetRessource):
    @InjectInConstructor
    def __init__(self,) -> None:
        super().__init__("sms/ongoing")
