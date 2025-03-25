
import time
from typing import Annotated
from fastapi import Depends, HTTPException, Header, Query, Request,status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.classes.auth_permission import AuthPermission, ClientType, FuncMetaData, MustHave, MustHaveRoleSuchAs, RefreshPermission, Role, TokensModel, parse_authPermission_enum
from app.container import Get, InjectInMethod
from app.decorators.guards import AuthenticatedClientGuard, BlacklistClientGuard
from app.decorators.handlers import SecurityClientHandler, ServiceAvailabilityHandler, TortoiseHandler
from app.decorators.my_depends import GetClient, get_client_by_password,verify_admin_signature, verify_admin_token
from app.decorators.permissions import AdminPermission, JWTRefreshTokenPermission, JWTRouteHTTPPermission, same_client_authPermission
from app.decorators.pipes import ForceClientPipe, RefreshTokenPipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UseGuard, UseHandler, UseLimiter, UsePermission, UsePipe, UseRoles
from app.errors.security_error import AuthzIdMisMatchError, ClientDoesNotExistError,ClientTokenHeaderNotProvidedError
from app.interface.issue_auth import IssueAuthInterface
from app.models.security_model import ChallengeORM, ClientORM, raw_revoke_auth_token, raw_revoke_challenges
from app.services.admin_service import AdminService
from app.services.config_service import ConfigService
from app.services.security_service import JWTAuthService
from app.utils.dependencies import get_auth_permission, get_client_from_request, get_client_ip
from app.utils.constant import ConfigAppConstant


REFRESH_AUTH_PREFIX = 'refresh'   
GENERATE_AUTH_PREFIX = 'generate'
AUTH_PREFIX = 'auth'    


@UseHandler(TortoiseHandler)   
@UsePipe(ForceClientPipe)
@UseHandler(ServiceAvailabilityHandler,SecurityClientHandler)
@UsePermission(JWTRouteHTTPPermission(True))
@HTTPRessource(REFRESH_AUTH_PREFIX)
class RefreshAuthRessource(BaseHTTPRessource,IssueAuthInterface):
    
    @InjectInMethod
    def __init__(self,adminService:AdminService):
        BaseHTTPRessource.__init__(self)
        IssueAuthInterface.__init__(self,adminService)

    @UseLimiter(limit_value='1/day')  # VERIFY Once a month
    @UsePipe(RefreshTokenPipe)
    @UseRoles(roles=[Role.REFRESH])
    @UsePermission(JWTRefreshTokenPermission)
    @UseGuard(BlacklistClientGuard, AuthenticatedClientGuard,)
    @BaseHTTPRessource.HTTPRoute('/client/', methods=[HTTPMethod.GET, HTTPMethod.POST], deprecated=True)
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
    @BaseHTTPRessource.HTTPRoute('/admin/', methods=[HTTPMethod.GET, HTTPMethod.POST], dependencies=[Depends(verify_admin_token)], )
    async def refresh_admin_token(self,tokens:TokensModel, client: Annotated[ClientORM, Depends(get_client_from_request)], request: Request,client_id:str=Query(""), authPermission=Depends(get_auth_permission)):
        refreshPermission:RefreshPermission = tokens
        await raw_revoke_auth_token(client)
        auth_token, refresh_token = await self.issue_auth(client, authPermission)
        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": { "auth_token": auth_token,}, "message": "Tokens successfully refreshed"})

@UseRoles([Role.ADMIN])
@UseHandler(TortoiseHandler,ServiceAvailabilityHandler)
@HTTPRessource(GENERATE_AUTH_PREFIX)
class GenerateAuthRessource(BaseHTTPRessource,IssueAuthInterface):
    admin_roles = [Role.ADMIN,Role.CUSTOM,Role.CONTACTS,Role.SUBSCRIPTION,Role.REFRESH,Role.CLIENT]

    @InjectInMethod
    def __init__(self,adminService:AdminService,configService:ConfigService,jwtAuthService:JWTAuthService):
        BaseHTTPRessource.__init__(self)
        #BaseHTTPRessource.__init__(self,dependencies=[Depends(verify_admin_signature),Depends(verify_admin_token)])
        IssueAuthInterface.__init__(self,adminService)
        self.configService = configService
        self.jwtAutService = jwtAuthService

    async def _get_admin_client(self,)->ClientORM:
        
        client = await ClientORM.filter(client_type =ClientType.Admin).first()
        if client == None:
            raise ClientDoesNotExistError()
        
        if client.client_type != ClientType.Admin:
            raise ClientDoesNotExistError()
        
        return client

    def _create_admin_auth_permission(self,admin:ClientORM)->AuthPermission:
        return AuthPermission(roles=self.admin_roles,scope=admin.client_scope,allowed_assets=[],allowed_routes={}) #TODO add more routes
    
    def _decode_and_verify(self, client: ClientORM, x_client_token):
        authPermission: AuthPermission = self.jwtAutService.decode_token(x_client_token)
        
        if authPermission["client_id"] != str(client.client_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client ID mismatch")

        if authPermission['generation_id'] != self.jwtAutService.generation_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Generation ID mismatch")
        
        if authPermission["issued_for"] != client.issued_for:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Issued-for mismatch")
        
        # if authPermission['group_id'] != str(client.group.group_id):
        #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Group ID mismatch")

        return authPermission
    
    @UseLimiter(limit_value='1/day')
    @UseHandler(SecurityClientHandler)
    @BaseHTTPRessource.HTTPRoute('/admin/', methods=[HTTPMethod.GET])
    async def issue_admin_auth(self, request: Request,):
        #TODO Protect requests
        admin_client = await self._get_admin_client()
        await raw_revoke_challenges(admin_client)
        authPermission = self._create_admin_auth_permission(admin_client)
        auth_token, refresh_token = await self.issue_auth(admin_client,authPermission)
        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": {
            "refresh_token": refresh_token, "auth_token": auth_token}, "message": "Tokens successfully issued"})
    
    @UseLimiter(limit_value='1/day')
    @UsePipe(ForceClientPipe)
    @UseHandler(SecurityClientHandler)
    @UseRoles(roles=[Role.CLIENT]) # BUG need to revise
    @UseGuard(BlacklistClientGuard,AuthenticatedClientGuard)
    @BaseHTTPRessource.HTTPRoute('/client/authenticate/', methods=[HTTPMethod.POST])
    async def self_issue_by_connect(self,request:Request,client:Annotated[ClientORM,Depends(get_client_by_password)],x_client_token:str=Header(None)):
        if x_client_token == None:
            raise ClientTokenHeaderNotProvidedError

        authPermission:AuthPermission = self._decode_and_verify(client, x_client_token)
        parse_authPermission_enum(authPermission)
        challenge = await ChallengeORM.filter(client=client).first()

        if not self.compare_authz_id(challenge,authPermission['authz_id']):
            raise AuthzIdMisMatchError
        
        await raw_revoke_auth_token(client)
        auth_token, refresh_token = await self.issue_auth(client, authPermission)
        await client.save()
        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": {
            "refresh_token": refresh_token, "auth_token": auth_token}, "message": "Tokens successfully issued"})

    @UsePipe(ForceClientPipe)
    @UseLimiter(limit_value='1/day')
    @UseHandler(SecurityClientHandler)
    @UseGuard(AuthenticatedClientGuard)
    @UseRoles(roles=[Role.CLIENT]) # BUG need to revise
    @BaseHTTPRessource.HTTPRoute('/client/authenticate/', methods=[HTTPMethod.DELETE])
    async def self_revoke_by_connect(self,request:Request,client:Annotated[ClientORM,Depends(get_client_by_password)],x_client_token:str=Header(None),ip_address:str=Depends(get_client_ip)):
        if x_client_token == None:
            raise ClientTokenHeaderNotProvidedError 

        authPermission:AuthPermission = self.jwtAutService.verify_auth_permission(x_client_token,ip_address)
        parse_authPermission_enum(authPermission)

        jwtAuthPermission = JWTRouteHTTPPermission(accept_inactive=True)
        challenge = await ChallengeORM.filter(client=client).first()

        if challenge.challenge_auth != authPermission['challenge']:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Challenge does not match") 
        
        funcMetaData:FuncMetaData = getattr(self.self_revoke_by_connect,'meta')
        jwtAuthPermission.permission(self.__class__.__name__,funcMetaData,authPermission)
        await self._revoke_client(client)
        return JSONResponse(status_code=status.HTTP_200_OK,content={'message':'Successfully disconnect'})


@HTTPRessource(AUTH_PREFIX,routers=[GenerateAuthRessource,RefreshAuthRessource])
class AuthRessource(BaseHTTPRessource):

    @UseLimiter(limit_value='1/week')
    @UsePermission(JWTRouteHTTPPermission,AdminPermission,same_client_authPermission)
    @BaseHTTPRessource.Get('/{client_id}')
    def route(self,client_id:str,request:Request,client:Annotated[ClientORM,Depends(get_client_from_request)],authPermission=Depends(get_auth_permission)):
        return 