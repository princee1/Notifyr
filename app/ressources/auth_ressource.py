
from typing import Annotated
from fastapi import Depends, Header, Query, Request,status
from fastapi.responses import JSONResponse
from app.classes.auth_permission import MustHave, Role, TokensModel
from app.container import Get, InjectInMethod
from app.decorators.guards import AuthenticatedClientGuard, BlacklistClientGuard, RefreshTokenGuard
from app.decorators.handlers import SecurityClientHandler, ServiceAvailabilityHandler, TortoiseHandler
from app.decorators.my_depends import GetClient, verify_admin_token
from app.decorators.permissions import AdminPermission, JWTRouteHTTPPermission, same_client_authPermission
from app.decorators.pipes import ForceClientPipe, RefreshTokenPipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UseGuard, UseHandler, UseLimiter, UsePermission, UsePipe, UseRoles
from app.interface.issue_auth import IssueAuthInterface
from app.models.security_model import ClientORM, raw_revoke_auth_token, raw_revoke_challenges
from app.services.admin_service import AdminService
from app.services.config_service import ConfigService
from app.services.security_service import SecurityService
from app.utils.dependencies import get_auth_permission

CLIENT_AUTH_PREFIX = 'client'   
ADMIN_AUTH_PREFIX = 'admin'
AUTH_PREFIX = 'auth'    


async def verify_admin_signature(x_admin_signature:Annotated[str,Header()]):
    adminService:AdminService = Get(AdminService)
    securityService:SecurityService = Get(SecurityService)
    configService:ConfigService = Get(ConfigService)

    if x_admin_signature == None:
        raise ...

    if securityService.verify_admin_signature():
        ...

@UseHandler(TortoiseHandler)   
@UsePipe(ForceClientPipe, RefreshTokenPipe)
@UseHandler(ServiceAvailabilityHandler,SecurityClientHandler)
@UsePermission(JWTRouteHTTPPermission(True),same_client_authPermission)
@HTTPRessource(CLIENT_AUTH_PREFIX)
class ClientAuthRessource(BaseHTTPRessource,IssueAuthInterface):
    
    @InjectInMethod
    def __init__(self,adminService:AdminService):
        BaseHTTPRessource.__init__(self)
        IssueAuthInterface.__init__(self,adminService)

    @UseLimiter(limit_value='1/day')  # VERIFY Once a month
    @UseRoles(roles=[Role.REFRESH])
    @UseGuard(BlacklistClientGuard, AuthenticatedClientGuard, RefreshTokenGuard)
    @BaseHTTPRessource.HTTPRoute('/refresh-auth/', methods=[HTTPMethod.GET, HTTPMethod.POST], deprecated=True)
    async def refresh_auth_token(self,tokens:TokensModel, client: Annotated[ClientORM, Depends(GetClient(True,False))], request: Request,client_id:str=Query(""), authPermission=Depends(get_auth_permission)):
        await raw_revoke_auth_token(client)
        auth_token, _ = await self.issue_auth(client, authPermission)
        client.authenticated = True # NOTE just to make sure
        await client.save()
        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": { "auth_token": auth_token}, "message": "Tokens successfully refreshed"})


    @UseLimiter(limit_value='1/day')  # VERIFY Once a month
    @UseGuard(RefreshTokenGuard)
    @UseRoles(roles=[Role.ADMIN],options=[MustHave(Role.ADMIN)])
    @UsePermission(AdminPermission)
    @BaseHTTPRessource.HTTPRoute('/refresh-admin-auth/', methods=[HTTPMethod.GET, HTTPMethod.POST], dependencies=[Depends(verify_admin_token)], )
    async def refresh_admin_token(self,tokens:TokensModel, client: Annotated[ClientORM, Depends(GetClient(False,True))], request: Request,client_id:str=Query(""), authPermission=Depends(get_auth_permission)):
        await raw_revoke_auth_token(client)
        auth_token, _ = await self.issue_auth(client, authPermission)
        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": { "auth_token": auth_token,}, "message": "Tokens successfully refreshed"})
   
@UseHandler(TortoiseHandler,ServiceAvailabilityHandler)
@HTTPRessource(ADMIN_AUTH_PREFIX)
class AdminAuthRessource(BaseHTTPRessource,IssueAuthInterface):

    @InjectInMethod
    def __init__(self,adminService:AdminService):
        BaseHTTPRessource.__init__(self,dependencies=[Depends(verify_admin_signature),Depends(verify_admin_token)])
        IssueAuthInterface.__init__(self,adminService)

    def _get_admin_client(self,client_id:str)->ClientORM:
        ... 

    def _create_auth_model(self,):
        ...       

    @BaseHTTPRessource.HTTPRoute('/issue-auth/{client_id}', methods=[HTTPMethod.GET])
    async def issue_admin_auth(self,client_id:str, request: Request,):
        admin_client = self._get_admin_client(client_id)
        await raw_revoke_challenges(admin_client)
        authModel = self._create_auth_model()
        auth_token, refresh_token = await self.issue_auth(admin_client, authModel)
        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": {
            "refresh_token": refresh_token, "auth_token": auth_token}, "message": "Tokens successfully issued"})
  
@HTTPRessource(AUTH_PREFIX,routers=[AdminAuthRessource,ClientAuthRessource])
class AuthRessource(BaseHTTPRessource):
    ...