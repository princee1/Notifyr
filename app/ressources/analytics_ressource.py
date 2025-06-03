
from fastapi import Depends, Request
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPRessource, UsePermission
from app.depends.dependencies import get_auth_permission


@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('analytics')
class AnalyticsRessource(BaseHTTPRessource):

    
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
