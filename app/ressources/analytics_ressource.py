
from fastapi import Depends, Request, Response
from app.classes.auth_permission import AccessAPIInfo, AuthPermission, ClientAccessInfo, Role
from app.decorators.handlers import AsyncIOHandler, TortoiseHandler
from app.decorators.permissions import ClientTypesPermission, JWTRouteHTTPPermission, UserPermission
from app.definition._ressource import BaseHTTPRessource, HTTPRessource, PingService, LockService, UseAccess, UseHandler, UsePermission, UseRoles,HTTPMethod
from app.depends.dependencies import get_access_info, get_auth_permission, get_client_info
from app.services.database.tortoise_service import TortoiseConnectionService

@UseRoles([Role.PUBLIC])
@PingService([TortoiseConnectionService])
@UseHandler(TortoiseHandler,AsyncIOHandler)
@UseAccess(accesses={'Admin':True,'User':True})
@UsePermission(JWTRouteHTTPPermission,UserPermission())
@LockService(TortoiseConnectionService,lockType='reader',infinite_wait=True)
@HTTPRessource('analytics')
class AnalyticsRessource(BaseHTTPRessource):

    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.OPTIONS])
    def analytics_options(self):
        return {}
    
    @BaseHTTPRessource.Get('/email/')
    async def fetch_email_analytics(self,response:Response, request: Request, authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info), accessInfo:AccessAPIInfo = Depends(get_access_info) ):
        return

    @BaseHTTPRessource.Get('/twilio/sms/')
    async def fetch_twilio_sms_analytics(self,response:Response, request: Request, authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info), accessInfo:AccessAPIInfo = Depends(get_access_info) ):
        return

    @BaseHTTPRessource.Get('/twilio/call/')
    async def fetch_twilio_call_analytics(self,response:Response, request: Request, authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info), accessInfo:AccessAPIInfo = Depends(get_access_info) ):
        return

    @BaseHTTPRessource.Get('/links/')
    async def fetch_links_analytics(self,response:Response, request: Request, authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info), accessInfo:AccessAPIInfo = Depends(get_access_info) ):
        return

    @BaseHTTPRessource.Get('/contacts/')
    async def fetch_contacts_analytics(self,response:Response, request: Request, authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info), accessInfo:AccessAPIInfo = Depends(get_access_info) ):
        return

    @BaseHTTPRessource.Get('/campaign/')
    async def fetch_campaign_analytics(self,response:Response, request: Request, authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info), accessInfo:AccessAPIInfo = Depends(get_access_info) ):
        return