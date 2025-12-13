from app.classes.auth_permission import AuthPermission, Role
from app.container import InjectInMethod
from app.decorators.handlers import AsyncIOHandler, CostHandler, RedisHandler, ServiceAvailabilityHandler, TortoiseHandler
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPRessource, HTTPMethod, PingService, UseHandler, UsePermission, UseRoles, UseServiceLock
from app.depends.dependencies import get_auth_permission
from app.services.cost_service import CostService
from app.services.database_service import RedisService, TortoiseConnectionService
from app.services.reactive_service import ReactiveService
from fastapi import Depends, Request, Response

from app.utils.constant import CostConstant


@PingService([CostService])
@UseHandler(ServiceAvailabilityHandler,AsyncIOHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('costs')
class CostRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,costService:CostService,reactiveService:ReactiveService,redisService:RedisService):
        super().__init__(None,None)
        self.costService = costService
        self.reactiveService = reactiveService
        self.redisService = redisService

    @UseRoles([Role.PUBLIC])
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.GET])
    def show_cost_file(self, request: Request, response: Response,authPermission:AuthPermission=Depends(get_auth_permission)):
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

    @UseRoles([Role.PUBLIC])
    @UseHandler(RedisHandler,CostHandler)
    @PingService([RedisService])
    @UseServiceLock(RedisService)
    @BaseHTTPRessource.HTTPRoute('/credits/', methods=[HTTPMethod.GET])
    async def show_current_credits(self, request: Request,authPermission:AuthPermission=Depends(get_auth_permission)):
        """Return current credits for all plan keys. May be restricted in production via permissions in future.
        """
        return await self.costService.get_all_credits_balance()


    @UseRoles([Role.ADMIN])
    @UseHandler(CostHandler)
    @PingService([CostService,RedisService])
    @BaseHTTPRessource.HTTPRoute('/history/{credit}', methods=[HTTPMethod.GET],)
    def history(self,credit:CostConstant.Credit, request: Request,authPermission:AuthPermission=Depends(get_auth_permission)):
        """Placeholder for billing/history endpoint. Implement retrieval from DB/audit store when available."""
        credit_key = self.costService.receipts_key(credit)
        
        return {"history": [], "detail": "not implemented"}
    

    @UseRoles([Role.ADMIN])
    @UseHandler(CostHandler)
    @PingService([CostService,RedisService])
    @BaseHTTPRessource.HTTPRoute('/summary/{credit}', methods=[HTTPMethod.GET],)
    def history(self,credit:CostConstant.Credit, request: Request,authPermission:AuthPermission=Depends(get_auth_permission)):
        """Placeholder for summary endpoint. Implement retrieval from DB/audit store when available."""
        credit_key = f"notifyr/credit:receipt@{credit}/summary"

        return {"history": [], "detail": "not implemented"}