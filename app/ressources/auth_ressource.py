
import time
from typing import Annotated
from fastapi import Depends, HTTPException, Header, Query, Request,status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.classes.auth_permission import AuthPermission, ClientType, FuncMetaData, MustHave, MustHaveRoleSuchAs, RefreshPermission, Role, TokensModel, parse_authPermission_enum
from app.container import Get, InjectInMethod
from app.decorators.guards import AuthenticatedClientGuard, BlacklistClientGuard
from app.decorators.handlers import AsyncIOHandler, ORMCacheHandler, SecurityClientHandler, ServiceAvailabilityHandler, TortoiseHandler
from app.depends.funcs_dep import GetClient, get_client_by_password,verify_admin_signature, verify_admin_token,verify_twilio_token
from app.decorators.permissions import AdminPermission, JWTRefreshTokenPermission, JWTRouteHTTPPermission, TwilioPermission, UserPermission, same_client_authPermission
from app.decorators.pipes import ForceClientPipe, RefreshTokenPipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, PingService, ServiceStatusLock, UseGuard, UseHandler, UseLimiter, UsePermission, UsePipe, UseRoles
from app.depends.orm_cache import ChallengeORMCache, ClientORMCache
from app.errors.security_error import AuthzIdMisMatchError, ClientDoesNotExistError,ClientTokenHeaderNotProvidedError, CouldNotCreateAuthTokenError
from app.interface.issue_auth import IssueAuthInterface
from app.models.security_model import ChallengeORM, ClientORM, raw_revoke_auth_token, raw_revoke_challenges
from app.services.admin_service import AdminService
from app.services.config_service import ConfigService
from app.services.database_service import TortoiseConnectionService
from app.services.security_service import JWTAuthService
from app.services.setting_service import SettingService
from app.services.twilio_service import TwilioService
from app.depends.dependencies import get_auth_permission, get_client_from_request, get_client_ip
from app.utils.constant import ConfigAppConstant
from tortoise.transactions import in_transaction


REFRESH_AUTH_PREFIX = 'refresh'   
GENERATE_AUTH_PREFIX = 'generate'
AUTH_PREFIX = 'auth'    

@ServiceStatusLock(TortoiseConnectionService,'reader',infinite_wait=True)
@UseHandler(TortoiseHandler)   
@UsePipe(ForceClientPipe)
@UseHandler(ServiceAvailabilityHandler,SecurityClientHandler,AsyncIOHandler)
@UsePermission(JWTRouteHTTPPermission(True))
@HTTPRessource(REFRESH_AUTH_PREFIX)
class RefreshAuthRessource(BaseHTTPRessource,IssueAuthInterface):
    
    @InjectInMethod
    def __init__(self,adminService:AdminService,twilioService:TwilioService):
        BaseHTTPRessource.__init__(self)
        IssueAuthInterface.__init__(self,adminService)
        self.twilioService = twilioService

    @UseLimiter(limit_value='1/day')  # VERIFY Once a month
    @UsePipe(RefreshTokenPipe)
    @UseRoles(roles=[Role.REFRESH])
    @UseHandler(ORMCacheHandler)
    @ServiceStatusLock(SettingService,'reader')
    @UsePermission(UserPermission,JWTRefreshTokenPermission)
    @UseGuard(BlacklistClientGuard, AuthenticatedClientGuard,)
    @BaseHTTPRessource.HTTPRoute('/client/', methods=[HTTPMethod.GET, HTTPMethod.POST])
    async def refresh_auth_token(self,tokens:TokensModel, client: Annotated[ClientORM, Depends(get_client_from_request)], request: Request,client_id:str=Query(""), authPermission=Depends(get_auth_permission)):
        refreshPermission:RefreshPermission = tokens
        async with in_transaction():    
            await raw_revoke_auth_token(client)
            auth_token, refresh_token = await self.issue_auth(client, authPermission)
            client.authenticated = True # NOTE just to make sure
            await client.save()

        await ChallengeORMCache.Invalid(client.client_id)
        await ClientORMCache.Invalid(client.client_id)
        
        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": { "auth_token": auth_token}, "message": "Tokens successfully refreshed"})


    @UseLimiter(limit_value='1/day')  # VERIFY Once a month
    @UsePipe(RefreshTokenPipe)
    @UseHandler(ORMCacheHandler)
    @ServiceStatusLock(SettingService,'reader')
    @UseRoles(roles=[Role.ADMIN,Role.REFRESH],options=[MustHave(Role.ADMIN)])
    @UsePermission(AdminPermission,JWTRefreshTokenPermission)
    @BaseHTTPRessource.HTTPRoute('/admin/', methods=[HTTPMethod.GET, HTTPMethod.POST], dependencies=[Depends(verify_admin_signature)], )
    async def refresh_admin_token(self,tokens:TokensModel, client: Annotated[ClientORM, Depends(get_client_from_request)], request: Request,client_id:str=Query(""), authPermission=Depends(get_auth_permission)):
        async with in_transaction():    

            refreshPermission:RefreshPermission = tokens
            await raw_revoke_auth_token(client)
            auth_token, refresh_token = await self.issue_auth(client, authPermission)

        await ClientORMCache.Invalid(client.client_id)
        
        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": { "auth_token": auth_token,}, "message": "Tokens successfully refreshed"})
    

    @UsePipe(RefreshTokenPipe)
    @UseHandler(SecurityClientHandler)
    @ServiceStatusLock(SettingService,'reader')
    @UseRoles(roles=[Role.ADMIN,Role.REFRESH,Role.TWILIO],options=[MustHaveRoleSuchAs(Role.ADMIN,Role.TWILIO)])
    @UsePermission(TwilioPermission,JWTRefreshTokenPermission)
    @BaseHTTPRessource.HTTPRoute('/admin/', methods=[HTTPMethod.GET, HTTPMethod.POST], dependencies=[Depends(verify_twilio_token)],mount=False )
    async def refresh_twilio_token(self,tokens:TokensModel, client: Annotated[ClientORM, Depends(get_client_from_request)], request: Request,client_id:str=Query(""), authPermission=Depends(get_auth_permission)):
        async with in_transaction():    
            refreshPermission:RefreshPermission = tokens
            await raw_revoke_auth_token(client)
            auth_token, refresh_token = await self.issue_auth(client, authPermission)

        status_code = await self.twilioService.update_env_variable(auth_token, refresh_token)

        if status_code == status.HTTP_200_OK:
                return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": {
            "refresh_token": refresh_token, "auth_token": auth_token}, "message": "Tokens successfully issued"})
        else:
            return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED,content='Could not set auth and refresh token')

@ServiceStatusLock(TortoiseConnectionService,'reader',infinite_wait=True)
@UseRoles([Role.ADMIN])
@UseHandler(TortoiseHandler,ServiceAvailabilityHandler,AsyncIOHandler)
@HTTPRessource(GENERATE_AUTH_PREFIX)
class GenerateAuthRessource(BaseHTTPRessource,IssueAuthInterface):
    admin_roles = [Role.ADMIN,Role.CUSTOM,Role.CONTACTS,Role.SUBSCRIPTION,Role.REFRESH,Role.CLIENT,Role.PUBLIC]
    twilio_roles = admin_roles + [Role.TWILIO]

    @InjectInMethod
    def __init__(self,adminService:AdminService,configService:ConfigService,jwtAuthService:JWTAuthService,twilioService:TwilioService):
        BaseHTTPRessource.__init__(self)
        #BaseHTTPRessource.__init__(self,dependencies=[Depends(verify_admin_signature),Depends(verify_admin_token)])
        IssueAuthInterface.__init__(self,adminService)
        self.configService = configService
        self.jwtAutService = jwtAuthService
        self.twilioService = twilioService

    async def _get_client_by_type(self,client_type)->ClientORM:
        
        client = await ClientORM.filter(client_type =client_type).first()
        if client == None:
            raise ClientDoesNotExistError()
                
        return client

    def _create_superuser_auth_permission(self,admin:ClientORM,roles,allowed_assets=[],allowed_routes={})->AuthPermission:
        return AuthPermission(roles=roles,scope=admin.client_scope,allowed_assets=allowed_assets,allowed_routes=allowed_routes) #TODO add more routes
    
    def _decode_and_verify(self, client: ClientORM, x_client_token):
        authPermission: AuthPermission = self.jwtAutService._decode_token(x_client_token)
        
        if authPermission["client_id"] != str(client.client_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client ID mismatch")

        if authPermission['generation_id'] != self.jwtAutService.GENERATION_ID:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Generation ID mismatch")
        
        if authPermission["issued_for"] != client.issued_for:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Issued-for mismatch")
        
        # if authPermission['group_id'] != str(client.group_id):  # VERIFY if works
        #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Group ID mismatch")

        return authPermission
    
    async def _create_superuser_auth(self,client_type,roles):
        async with in_transaction():
            client = await self._get_client_by_type(client_type)
            await raw_revoke_challenges(client)
            authPermission = self._create_superuser_auth_permission(client,roles)
            auth_token, refresh_token = await self.issue_auth(client,authPermission)
        
        if auth_token == None:
            raise CouldNotCreateAuthTokenError
    
        await ChallengeORMCache.Invalid(client.client_id)

        return auth_token, refresh_token

    @UseLimiter(limit_value='1/day')
    @UseHandler(SecurityClientHandler,ORMCacheHandler)
    @ServiceStatusLock(SettingService,'reader')
    @BaseHTTPRessource.HTTPRoute('/admin/', methods=[HTTPMethod.GET],dependencies=[Depends(verify_admin_signature),Depends(verify_admin_token)])
    async def issue_admin_auth(self, request: Request,):
        #TODO Protect requests
        auth_token, refresh_token = await self._create_superuser_auth(ClientType.Admin,self.admin_roles)

        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": {
            "refresh_token": refresh_token, "auth_token": auth_token}, "message": "Tokens successfully issued"})
    
    @UseLimiter(limit_value='1/day')
    @UseHandler(SecurityClientHandler,ORMCacheHandler)
    @ServiceStatusLock(SettingService,'reader')
    @BaseHTTPRessource.HTTPRoute('/twilio/', methods=[HTTPMethod.GET],dependencies=[Depends(verify_admin_signature),Depends(verify_admin_token)],mount=False)
    async def issue_twilio_auth(self,request:Request):
        
        auth_token, refresh_token = await self._create_superuser_auth(ClientType.Twilio,self.twilio_roles)
        status_code = await self.twilioService.update_env_variable(auth_token,refresh_token)

        if status_code == status.HTTP_200_OK:
                return JSONResponse(status_code=status.HTTP_200_OK, content={ "message": "Tokens successfully issued"})
        else:
            return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,content='Could not set auth and refresh token')
        
    @UseLimiter(limit_value='1/day',per_method=True)
    @UsePipe(ForceClientPipe)
    @UseHandler(SecurityClientHandler,ORMCacheHandler)
    @UseRoles(roles=[Role.CLIENT]) # BUG need to revise
    @UseGuard(BlacklistClientGuard,AuthenticatedClientGuard)
    @ServiceStatusLock(SettingService,'reader')
    @UsePermission(UserPermission(accept_none_auth=True))
    @BaseHTTPRessource.HTTPRoute('/client/authenticate/', methods=[HTTPMethod.POST])
    async def self_issue_by_connect(self,request:Request,client:Annotated[ClientORM,Depends(get_client_by_password)],x_client_token:str=Header(None)):
        if x_client_token == None:
            raise ClientTokenHeaderNotProvidedError

        authPermission:AuthPermission = self._decode_and_verify(client, x_client_token)
        parse_authPermission_enum(authPermission)
        async with in_transaction():    

            challenge = await ChallengeORM.filter(client=client).first()
            if not self.compare_authz_id(challenge,authPermission['authz_id']):
                raise AuthzIdMisMatchError
            
            await raw_revoke_auth_token(client)
            auth_token, refresh_token = await self.issue_auth(client, authPermission)
            
            await client.save()

        await ChallengeORMCache.Invalid(client.client_id)
        
        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": {
            "refresh_token": refresh_token, "auth_token": auth_token}, "message": "Tokens successfully issued"})

    @UsePipe(ForceClientPipe)
    @UseLimiter(limit_value='1/day',per_method=True)
    @UseHandler(SecurityClientHandler,ORMCacheHandler)
    @UseGuard(AuthenticatedClientGuard)
    @UsePermission(UserPermission(accept_none_auth=True))
    @UseRoles(roles=[Role.CLIENT]) # BUG need to revise
    @BaseHTTPRessource.HTTPRoute('/client/authenticate/', methods=[HTTPMethod.DELETE])
    async def self_revoke_by_connect(self,request:Request,client:Annotated[ClientORM,Depends(get_client_by_password)],x_client_token:str=Header(None),ip_address:str=Depends(get_client_ip)):
        if x_client_token == None:
            raise ClientTokenHeaderNotProvidedError 

        authPermission:AuthPermission = self.jwtAutService.verify_auth_permission(x_client_token,ip_address)
        parse_authPermission_enum(authPermission)

        async with in_transaction():    
            jwtAuthPermission = JWTRouteHTTPPermission(accept_inactive=True)
            challenge = await ChallengeORM.filter(client=client).first()

            if challenge.challenge_auth != authPermission['challenge']:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Challenge does not match") 
            
            funcMetaData:FuncMetaData = getattr(self.self_revoke_by_connect,'meta')
            jwtAuthPermission.permission(self.__class__.__name__,funcMetaData,authPermission)
            await self._revoke_client(client)

        await ChallengeORMCache.Invalid(client.client_id)
        
        return JSONResponse(status_code=status.HTTP_200_OK,content={'message':'Successfully disconnect'})


@HTTPRessource(AUTH_PREFIX,routers=[GenerateAuthRessource,RefreshAuthRessource])
class AuthRessource(BaseHTTPRessource):

    @UseLimiter(limit_value='1/week')
    @UsePermission(JWTRouteHTTPPermission,AdminPermission,same_client_authPermission)
    @BaseHTTPRessource.Get('/{client_id}')
    def route(self,client_id:str,request:Request,client:Annotated[ClientORM,Depends(get_client_from_request)],authPermission=Depends(get_auth_permission)):
        return 