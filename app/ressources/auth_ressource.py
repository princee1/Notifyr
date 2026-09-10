from typing import Annotated
from fastapi import Depends, Request, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette import status
from app.classes.auth_permission import AccessModel, AuthPermission, AuthType, ClientAccessInfo, ClientRefresh
from app.container import InjectInMethod
from app.decorators.guards import AuthenticationClientGuard, BlacklistClientGuard, ClientAuthTypeGuard
from app.decorators.handlers import AuthClientHandler, MiniServiceHandler, ORMCacheHandler, RedisHandler, SecurityHandler, VaultHandler
from app.decorators.permissions import JWTRouteHTTPPermission, UserPermission
from app.decorators.pipes import AccessTokenModelPipe, MiniServiceInjectorPipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, LockService, PingService, Throttle, UseGuard, UseHandler, UsePermission, UsePipe
from app.definition._service import MiniStateProtocol
from app.depends.dependencies import get_auth_permission, get_client_info, get_client_ip
from app.depends.funcs_dep import get_client_from_info
from app.errors.security_error import ClientAuthenticationFlagError, ClientDoesNotExistError
from app.manager.broker_manager import Broker
from app.manager.session_manager import AuthSessionManager
from app.models.orm.security_model import ClientORM
from app.services.admin_service import AdminService, AuthSignature, ClientMiniService
from app.services.database.redis_service import RedisService
from app.services.database.tortoise_service import TortoiseConnectionService
from app.services.security_service import JWTAuthService
from app.services.setting_service import SettingService
from app.services.vault_service import VaultService
from tortoise.expressions import Q

@PingService([VaultService])
@UseHandler(VaultHandler,AuthClientHandler)
@HTTPRessource('auth')
class AuthRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,tortoiseService:TortoiseConnectionService,adminService:AdminService):
        super().__init__(None,None)
        self.tortoiseService = tortoiseService
        self.adminService = adminService
        self.blacklist_guard = BlacklistClientGuard()

    
    @Throttle(uniform=(100,250))
    @BaseHTTPRessource.HTTPRoute('/recover/',methods=[HTTPMethod.POST])
    async def recover(self,broker:Annotated[Broker,Depends(Broker)],session:Annotated[AuthSessionManager,Depends(AuthSessionManager)]):
        ...

    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @LockService(VaultService,SettingService,JWTAuthService,lockType='reader')
    @UseHandler(ORMCacheHandler,MiniServiceHandler,SecurityHandler,RedisHandler)
    @BaseHTTPRessource.HTTPRoute('/refresh/',methods=[HTTPMethod.PUT])
    async def refresh(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],session:Annotated[AuthSessionManager,Depends(AuthSessionManager)]):
        refreshPermission:ClientRefresh =  session.verify_refresh_token()

        clientORM = await ClientORM.filter(client_id=refreshPermission['client_id']).first()
        if clientORM == None:
            raise ClientDoesNotExistError(refreshPermission['client_id'])
        
        if clientORM.auth_type != AuthType.ACCESS_TOKEN:
            raise ClientDoesNotExistError(refreshPermission['client_id'])

        if not clientORM.authenticated:
            raise ClientAuthenticationFlagError(refreshPermission['client_id'],False)

        origin = get_client_ip(request)

        async with self.adminService.lock('reader',clientORM.client_id) as client:
            async with self.tortoiseService.transaction() as ctx:
                self.blacklist_guard.guard(client)
                client.verify_client_origin(origin)

                signature = client.compare_auth_signature(refreshPermission['authz_id'])
                auth_token,refresh_token = await client.generate_access(signature,ctx=ctx)
                session.login(refresh_token)

        broker.propagate(MiniStateProtocol(service=AdminService,to_build=True,id=client.miniService_id  ))
        return {'access':auth_token,'auth_type':AuthType.ACCESS_TOKEN}

    @Throttle(normal=(300,30))
    @UseHandler(ORMCacheHandler,MiniServiceHandler,SecurityHandler,RedisHandler)
    @LockService(VaultService,SettingService,JWTAuthService,RedisService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/login/',methods=[HTTPMethod.POST],response_class=AccessModel)
    async def login(self,broker:Annotated[Broker,Depends(Broker)],request:Request,response:Response, credentials: Annotated[HTTPBasicCredentials, Depends(HTTPBasic())],session:Annotated[AuthSessionManager,Depends(AuthSessionManager)]):
        
        clientORM = await ClientORM.filter(Q(column1=credentials.username) | Q(column2=credentials.username)).first()
        if clientORM == None:
            raise ClientDoesNotExistError(credentials.username)
        
        if clientORM.auth_type != AuthType.ACCESS_TOKEN:
            raise ClientDoesNotExistError(credentials.username)

        if clientORM.authenticated:
            raise ClientAuthenticationFlagError(credentials.username,True)

        origin = get_client_ip(request)
            
        async with self.adminService.lock('reader',clientORM.client_id) as client:

            async with self.tortoiseService.transaction() as ctx:
                self.blacklist_guard.guard(client)
                client.verify_client_origin(origin)

                await client.compare_password(credentials.password)
                authSignature:AuthSignature = client.signature.to_plain()
                auth_token,refresh_token = await client.generate_access(authSignature['signature'],ctx=ctx)
                session.login(refresh_token)
        
        broker.propagate(MiniStateProtocol(service=AdminService,to_build=True,id=client.miniService_id  ))
        return {'access':auth_token,'auth_type':AuthType.ACCESS_TOKEN}

    @Throttle(uniform=(200,400))
    @UseHandler(MiniServiceHandler)
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @LockService(VaultService,AdminService,as_manager=True)
    @UsePipe(MiniServiceInjectorPipe(AdminService,'client'))
    @UsePermission(JWTRouteHTTPPermission(True),UserPermission)
    @UseGuard(ClientAuthTypeGuard(accept_access=True, accept_api=False), AuthenticationClientGuard(True))
    @BaseHTTPRessource.HTTPRoute('/logout/',methods=[HTTPMethod.POST])
    async def logout(self,broker:Annotated[Broker,Depends(Broker)],client:Annotated[ClientMiniService,Depends(get_client_from_info)],session:Annotated[AuthSessionManager,Depends(AuthSessionManager)],profile:str=Depends(get_client_from_info),authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):
        async with self.tortoiseService.transaction() as ctx:
            await client.revoke_itself(ctx,authenticated=False)
            session.logout()
        
        return

    @Throttle(normal=(300,30))
    @UseHandler(MiniServiceHandler)
    @UsePermission(JWTRouteHTTPPermission,UserPermission)
    @UsePipe(MiniServiceInjectorPipe(AdminService,'client'))
    @LockService(AdminService,as_manager=True,lockType='reader',miniLockType='reader')
    @UseGuard(ClientAuthTypeGuard(accept_access=True, accept_api=False), AuthenticationClientGuard(True),BlacklistClientGuard)
    @BaseHTTPRessource.HTTPRoute('/me/',methods=[HTTPMethod.GET])
    async def me(self,request:Request,response:Response,client:Annotated[ClientMiniService,Depends(get_client_from_info)],profile:str=Depends(get_client_from_info),authPermission:AuthPermission=Depends(get_auth_permission),clientInfo:ClientAccessInfo=Depends(get_client_info)):

        info = client.client.to_json
        policies = client.authPermission

        return {'client':info,'policies':policies}

    
    