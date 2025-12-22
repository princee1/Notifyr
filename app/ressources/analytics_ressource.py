
from fastapi import Depends, Request
from app.classes.auth_permission import Role
from app.decorators.handlers import AsyncIOHandler, TortoiseHandler
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPRessource, PingService, UseServiceLock, UseHandler, UsePermission, UseRoles,HTTPMethod
from app.depends.dependencies import get_auth_permission
from app.services.database.tortoise_service import TortoiseConnectionService

@PingService([TortoiseConnectionService])
@UseServiceLock(TortoiseConnectionService,lockType='reader',infinite_wait=True)
@UseRoles([Role.ADMIN])
@UseHandler(TortoiseHandler,AsyncIOHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('analytics')
class AnalyticsRessource(BaseHTTPRessource):

    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.OPTIONS])
    def analytics_options(self):
        return {

        }
    
    @BaseHTTPRessource.Get('/email/', mount=False)
    async def fetch_email_analytics(self, request: Request, authPermission=Depends(get_auth_permission)):
        return

    @BaseHTTPRessource.Get('/twilio/sms/', mount=False)
    async def fetch_twilio_sms_analytics(self, request: Request, authPermission=Depends(get_auth_permission)):
        return

    @BaseHTTPRessource.Get('/twilio/call/', mount=False)
    async def fetch_twilio_call_analytics(self, request: Request, authPermission=Depends(get_auth_permission)):
        return

    @BaseHTTPRessource.Get('/links/', mount=False)
    async def fetch_links_analytics(self, request: Request, authPermission=Depends(get_auth_permission)):
        return

    @BaseHTTPRessource.Get('/server/', mount=False)
    async def fetch_server_analytics(self, request: Request, authPermission=Depends(get_auth_permission)):
        return

    @BaseHTTPRessource.Get('/contacts/', mount=False)
    async def fetch_contacts_analytics(self, request: Request, authPermission=Depends(get_auth_permission)):
        return

    @BaseHTTPRessource.Get('/campaign/', mount=False)
    async def fetch_campaign_analytics(self, request: Request, authPermission=Depends(get_auth_permission)):
        return