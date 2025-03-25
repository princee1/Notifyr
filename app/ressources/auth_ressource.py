
import time
from typing import Annotated
from fastapi import Depends, Header, Query, Request,status
from fastapi.responses import JSONResponse
from app.classes.auth_permission import AuthPermission, ClientType, MustHave, RefreshPermission, Role, TokensModel
from app.container import Get, InjectInMethod
from app.decorators.guards import AuthenticatedClientGuard, BlacklistClientGuard
from app.decorators.handlers import SecurityClientHandler, ServiceAvailabilityHandler, TortoiseHandler
from app.decorators.my_depends import GetClient,verify_admin_signature, verify_admin_token
from app.decorators.permissions import AdminPermission, JWTRefreshTokenPermission, JWTRouteHTTPPermission, same_client_authPermission
from app.decorators.pipes import ForceClientPipe, RefreshTokenPipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UseGuard, UseHandler, UseLimiter, UsePermission, UsePipe, UseRoles
from app.errors.security_error import ClientDoesNotExistError
from app.interface.issue_auth import IssueAuthInterface
from app.models.security_model import ClientORM, raw_revoke_auth_token, raw_revoke_challenges
from app.services.admin_service import AdminService
from app.services.config_service import ConfigService
from app.utils.dependencies import get_auth_permission, get_client_from_request
from app.utils.constant import ConfigAppConstant

CLIENT_AUTH_PREFIX = 'client'   
ADMIN_AUTH_PREFIX = 'admin'
AUTH_PREFIX = 'auth'    


@UseHandler(TortoiseHandler)   
@UsePipe(ForceClientPipe)
@UseHandler(ServiceAvailabilityHandler,SecurityClientHandler)
@UsePermission(JWTRouteHTTPPermission(True))
@HTTPRessource(CLIENT_AUTH_PREFIX)
class ClientAuthRessource(BaseHTTPRessource,IssueAuthInterface):
    
    @InjectInMethod
    def __init__(self,adminService:AdminService):
        BaseHTTPRessource.__init__(self)
        IssueAuthInterface.__init__(self,adminService)

    @UseLimiter(limit_value='1/day')  # VERIFY Once a month
    @UsePipe(RefreshTokenPipe)
    @UseRoles(roles=[Role.REFRESH])
    @UsePermission(JWTRefreshTokenPermission)
    @UseGuard(BlacklistClientGuard, AuthenticatedClientGuard,)
    @BaseHTTPRessource.HTTPRoute('/refresh-auth/', methods=[HTTPMethod.GET, HTTPMethod.POST], deprecated=True)
    async def refresh_auth_token(self,tokens:TokensModel, client: Annotated[ClientORM, Depends(get_client_from_request)], request: Request,client_id:str=Query(""), authPermission=Depends(get_auth_permission)):
        refreshPermission:RefreshPermission = tokens
        await raw_revoke_auth_token(client)
        auth_token, refresh_token = await self.issue_auth(client, authPermission)
        client.authenticated = True # NOTE just to make sure
        await client.save()
        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": { "auth_token": auth_token}, "message": "Tokens successfully refreshed"})


    @UseLimiter(limit_value='1/day')  # VERIFY Once a month
    @UsePipe(RefreshTokenPipe)
    @UseRoles(roles=[Role.ADMIN,Role.REFRESH],options=[MustHave(Role.ADMIN)])
    @UsePermission(AdminPermission,JWTRefreshTokenPermission)
    @BaseHTTPRessource.HTTPRoute('/refresh-admin-auth/', methods=[HTTPMethod.GET, HTTPMethod.POST], dependencies=[Depends(verify_admin_token)], )
    async def refresh_admin_token(self,tokens:TokensModel, client: Annotated[ClientORM, Depends(get_client_from_request)], request: Request,client_id:str=Query(""), authPermission=Depends(get_auth_permission)):
        refreshPermission:RefreshPermission = tokens
        await raw_revoke_auth_token(client)
        auth_token, refresh_token = await self.issue_auth(client, authPermission)
        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": { "auth_token": auth_token,}, "message": "Tokens successfully refreshed"})
   
@UseHandler(TortoiseHandler,ServiceAvailabilityHandler)
@HTTPRessource(ADMIN_AUTH_PREFIX)
class AdminAuthRessource(BaseHTTPRessource,IssueAuthInterface):
    admin_roles = [Role.ADMIN,Role.CUSTOM,Role.CONTACTS,Role.SUBSCRIPTION,Role.REFRESH]

    @InjectInMethod
    def __init__(self,adminService:AdminService,configService:ConfigService):
        BaseHTTPRessource.__init__(self)
        #BaseHTTPRessource.__init__(self,dependencies=[Depends(verify_admin_signature),Depends(verify_admin_token)])
        IssueAuthInterface.__init__(self,adminService)
        self.configService = configService

    async def _get_admin_client(self,)->ClientORM:
        
        client = await ClientORM.filter(client_type =ClientType.Admin).first()
        if client == None:
            raise ClientDoesNotExistError()
        
        if client.client_type != ClientType.Admin:
            raise ClientDoesNotExistError()
        
        return client

    def _create_admin_auth_permission(self,admin:ClientORM)->AuthPermission:
        return AuthPermission(roles=self.admin_roles,scope=admin.client_scope,allowed_assets=[],allowed_routes={}) #TODO add more routes
    
    @UseLimiter(limit_value='1/day')
    @UseHandler(SecurityClientHandler)
    @BaseHTTPRessource.HTTPRoute('/issue-auth/', methods=[HTTPMethod.GET])
    async def issue_admin_auth(self, request: Request,):
        #TODO Protect requests
        admin_client = await self._get_admin_client()
        await raw_revoke_challenges(admin_client)
        authPermission = self._create_admin_auth_permission(admin_client)
        auth_token, refresh_token = await self.issue_auth(admin_client,authPermission)
        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": {
            "refresh_token": refresh_token, "auth_token": auth_token}, "message": "Tokens successfully issued"})
  

@HTTPRessource(AUTH_PREFIX,routers=[AdminAuthRessource,ClientAuthRessource])
class AuthRessource(BaseHTTPRessource):

    @UseLimiter(limit_value='1/week')
    @UsePermission(JWTRouteHTTPPermission,AdminPermission,same_client_authPermission)
    @BaseHTTPRessource.Get('/{client_id}')
    def route(self,client_id:str,request:Request,client:Annotated[ClientORM,Depends(get_client_from_request)],authPermission=Depends(get_auth_permission)):
        return 