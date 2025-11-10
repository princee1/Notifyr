from app.container import InjectInMethod
from app.definition._ressource import BaseHTTPRessource, HTTPRessource
from app.services.cost_service import CostService
from app.services.reactive_service import ReactiveService


@HTTPRessource('costs')
class CostRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,costService:CostService,reactiveService:ReactiveService):
        super().__init__(None,None)
        self.costService = costService
        self.reactiveService = reactiveService

