from app.container import InjectInMethod
from app.decorators.handlers import AsyncIOHandler, CostHandler, RedisHandler, ServiceAvailabilityHandler, TortoiseHandler
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPRessource, HTTPMethod, PingService, UseHandler, UsePermission, UseServiceLock
from app.services.cost_service import CostService
from app.services.database_service import RedisService, TortoiseConnectionService
from app.services.reactive_service import ReactiveService
from fastapi import Request, Response


@PingService([CostService])
@UseHandler(ServiceAvailabilityHandler,AsyncIOHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('costs')
class CostRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,costService:CostService,reactiveService:ReactiveService):
        super().__init__(None,None)
        self.costService = costService
        self.reactiveService = reactiveService

    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.GET])
    def show_cost_file(self, request: Request, response: Response):
        """Return a summary of the currently loaded cost definitions.
        Implementation note: this is a light placeholder — change to expose full file or a filtered view as needed.
        """
        return {
            "version": self.costService.version,
            "product": self.costService.product,
            "definitions":self.costService.costs_definition,
            "currency":self.costService.currency,
            "system":self.costService.system,
            "promotions":self.costService.promotions,
            "plan-credits":self.costService.plan_credits,
            "rules":self.costService.rules
        }

    @UseHandler(RedisHandler,CostHandler)
    @PingService(RedisService)
    @UseServiceLock(RedisService)
    @BaseHTTPRessource.HTTPRoute('/credits/', methods=[HTTPMethod.GET])
    async def show_current_credits(self, request: Request):
        """Return current credits for all plan keys. May be restricted in production via permissions in future.
        """
        return  await self.costService.get_current_credits()

    
    @UseHandler(TortoiseHandler,CostHandler)
    @PingService(TortoiseConnectionService)
    @UseServiceLock(TortoiseConnectionService)
    @BaseHTTPRessource.HTTPRoute('/history/', methods=[HTTPMethod.GET])
    def history(self, request: Request):
        """Placeholder for billing/history endpoint. Implement retrieval from DB/audit store when available."""
        return {"history": [], "detail": "not implemented"}