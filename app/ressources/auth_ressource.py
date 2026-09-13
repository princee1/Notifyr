from typing import Annotated
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette import status
from app.classes.auth_permission import AccessModel, AuthPermission, AuthType, ClientAccessInfo, ClientRefresh, ClientType, Credentials, EncryptedRecoveryTokens, RecoveryTokenGenerator, RecoveryTokens
from app.container import InjectInMethod
from app.decorators.guards import AuthenticationClientGuard, BlacklistClientGuard, ClientAuthTypeGuard
from app.decorators.handlers import AuthClientHandler, MiniServiceHandler, ORMCacheHandler, RedisHandler, SecurityHandler, VaultHandler
from app.decorators.interceptors import InvalidBlacklistTokenInterceptor
from app.decorators.permissions import JWTRouteHTTPPermission, UserPermission
from app.decorators.pipes import AccessTokenModelPipe, MiniServiceInjectorPipe, ObjectRelationalFriendlyPipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, LockService, PingService, Throttle, UseGuard, UseHandler, UseInterceptor, UseLimiter, UsePermission, UsePipe
from app.definition._service import MiniStateProtocol
from app.depends.dependencies import get_auth_permission, get_client_info, get_client_ip
from app.depends.funcs_dep import get_client_from_info
from app.depends.orm_cache import BlacklistClientCache
from app.errors.security_error import ClientAuthenticationFlagError, ClientDoesNotExistError
from app.manager.broker_manager import Broker
from app.manager.session_manager import AuthSessionManager
from app.models.orm.security_model import ClientORM, UpdateClientModel
from app.ressources.admin_ressource import ClientRessource
from app.services.admin_service import AdminService, AuthSignature, ClientMiniService
from app.services.database.redis_service import RedisService
from app.services.database.tortoise_service import SECURITY_CREDS, TortoiseConnectionService
from app.services.security_service import JWTAuthService
from app.services.setting_service import SettingService
from app.services.vault_service import VaultService
from tortoise.expressions import Q


async def refresh_logout_handler(func,*args,**kwargs):
    try:
        return await func(*args,**kwargs)
    except HTTPException as e:
        session:AuthSessionManager = kwargs.get('session',None)
        if session:
            session.logout()
        raise e

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

    @Throttle(normal=(300,30))
    @UseHandler(MiniServiceHandler)
    @UseLimiter('2/day',key_func='client')
    @UsePermission(JWTRouteHTTPPermission,UserPermission)
    @UsePipe(MiniServiceInjectorPipe(AdminService,'client'))
    @LockService(VaultService,AdminService,as_manager=True,lockType='reader',miniLockType='reader')
    @UseGuard(ClientAuthTypeGuard(accept_access=True, accept_api=False), AuthenticationClientGuard(True),BlacklistClientGuard)
    @BaseHTTPRessource.HTTPRoute('/recover/',methods=[HTTPMethod.GET])
    async def get_recovery_token(self,request:Request,response:Response,client:Annotated[ClientMiniService,Depends(get_client_from_info)],profile:str=Depends(get_client_from_info),authPermission:AuthPermission=Depends(get_auth_permission),clientInfo:ClientAccessInfo=Depends(get_client_info)):

        tokens = []
        recovery = RecoveryTokenGenerator()
        async for token in recovery.generate():
            encrypted_code,salt = await client.encrypt_password(token)
            tokens.append(Credentials(password=encrypted_code,salt=salt))

        encrypted_token = EncryptedRecoveryTokens(tokens=tokens,recovery_id=recovery.id)
        await client.create_recovery_code(encrypted_token)

        return recovery.export()

    @UseLimiter('5/day')
    @Throttle(normal=(300,30))
    @UseLimiter('5/day',key_func='ip')
    @UseHandler(ORMCacheHandler,MiniServiceHandler,SecurityHandler,RedisHandler)
    @LockService(VaultService,SettingService,JWTAuthService,RedisService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/recover/',methods=[HTTPMethod.POST],response_class = AccessModel)
    async def recover(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)], credentials: Annotated[HTTPBasicCredentials, Depends(HTTPBasic())],session:Annotated[AuthSessionManager,Depends(AuthSessionManager)]):
        session.logout()

        clientORM = await ClientORM.filter(Q(client_username=credentials.username) | Q(client_email=credentials.username)).first()
        self.verify_client(credentials.username, clientORM,True)
        origin = get_client_ip(request)

        async with self.adminService.lock('reader',clientORM.client_id) as client:
            async with self.tortoiseService.transaction() as ctx:

                self.blacklist_guard.guard(client)
                client.verify_client_origin(origin)

                await client.verify_recovery_code(credentials.password)
                new_signature = await client.revoke_itself(ctx=ctx,authenticated=True)
                auth_token,refresh_token = await client.generate_access(new_signature,ctx=ctx)

                await client.create_recovery_code({})
                session.login(refresh_token)

        broker.propagate(MiniStateProtocol(service=AdminService,to_build=True,id=client.miniService_id  ))
        return {'access':auth_token,'auth_type':AuthType.ACCESS_TOKEN}

    @Throttle(uniform=(100,250))
    @UseLimiter('5/day',key_func='ip')
    @UseHandler(refresh_logout_handler)
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @LockService(VaultService,SettingService,JWTAuthService,lockType='reader')
    @UseHandler(ORMCacheHandler,MiniServiceHandler,SecurityHandler,RedisHandler)
    @BaseHTTPRessource.HTTPRoute('/refresh/',methods=[HTTPMethod.PUT],response_class=AccessModel)
    async def refresh(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],session:Annotated[AuthSessionManager,Depends(AuthSessionManager)]):
        refreshPermission:ClientRefresh =  session.verify_refresh_token()
        session.logout()

        clientORM = await ClientORM.filter(client_id=refreshPermission['client_id']).first()
        self.verify_client(refreshPermission['client_id'], clientORM,False)
        origin = get_client_ip(request)

        async with self.adminService.lock('reader',clientORM.client_id) as client:
            async with self.tortoiseService.transaction() as ctx:

                self.blacklist_guard.guard(client)
                client.verify_client_origin(origin)
                client.compare_auth_signature(refreshPermission['authz_id'])

                new_signature = await client.revoke_itself(ctx=ctx,authenticated=True)
                auth_token,refresh_token = await client.generate_access(new_signature,ctx=ctx)
                session.login(refresh_token)

        broker.propagate(MiniStateProtocol(service=AdminService,to_build=True,id=client.miniService_id  ))
        return {'access':auth_token,'auth_type':AuthType.ACCESS_TOKEN}

    @UseLimiter('5/day')
    @Throttle(normal=(300,30))
    @UseHandler(ORMCacheHandler,MiniServiceHandler,SecurityHandler,RedisHandler)
    @LockService(VaultService,SettingService,JWTAuthService,RedisService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/login/',methods=[HTTPMethod.POST],response_class=AccessModel)
    async def login(self,broker:Annotated[Broker,Depends(Broker)],request:Request,response:Response, credentials: Annotated[HTTPBasicCredentials, Depends(HTTPBasic())],session:Annotated[AuthSessionManager,Depends(AuthSessionManager)]):
        
        clientORM = await ClientORM.filter(Q(client_username=credentials.username) | Q(client_email=credentials.username)).first()

        self.verify_client(credentials.username, clientORM,True)
        origin = get_client_ip(request)
            
        async with self.adminService.lock('reader',clientORM.client_id) as client:
            async with self.tortoiseService.transaction(SECURITY_CREDS) as ctx:

                self.blacklist_guard.guard(client)
                client.verify_client_origin(origin)

                encryptedPassword = await client.fetch_password()
                await client.compare_password(credentials.password,encryptedPassword)

                authSignature:AuthSignature = client.signature.to_plain()
                auth_token,refresh_token = await client.generate_access(authSignature['signature'],ctx=ctx)
                session.login(refresh_token)
        
        broker.propagate(MiniStateProtocol(service=AdminService,to_build=True,id=client.miniService_id  ))
        return {'access':auth_token,'auth_type':AuthType.ACCESS_TOKEN}

    @Throttle(uniform=(200,400))
    @UseLimiter('10/day',key_func='client')
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @UseInterceptor(InvalidBlacklistTokenInterceptor)
    @LockService(VaultService,AdminService,as_manager=True)
    @UsePipe(MiniServiceInjectorPipe(AdminService,'client'))
    @UsePermission(JWTRouteHTTPPermission(True),UserPermission)
    @UseHandler(ORMCacheHandler,MiniServiceHandler,SecurityHandler,RedisHandler)
    @UseGuard(ClientAuthTypeGuard(accept_access=True, accept_api=False), AuthenticationClientGuard(True))
    @BaseHTTPRessource.HTTPRoute('/logout/',methods=[HTTPMethod.POST])
    async def logout(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],client:Annotated[ClientMiniService,Depends(get_client_from_info)],session:Annotated[AuthSessionManager,Depends(AuthSessionManager)],profile:str=Depends(get_client_from_info),authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):
        async with self.tortoiseService.transaction() as ctx:
            await client.revoke_itself(ctx,authenticated=False)
            request.state.clear = True
            session.logout()

        return

    @Throttle(normal=(300,30))
    @UseHandler(MiniServiceHandler)
    @UseLimiter('20/day',key_func='client')
    @UsePermission(JWTRouteHTTPPermission,UserPermission)
    @UsePipe(MiniServiceInjectorPipe(AdminService,'client'))
    @LockService(AdminService,as_manager=True,lockType='reader',miniLockType='reader')
    @UseGuard(ClientAuthTypeGuard(accept_access=True, accept_api=False), AuthenticationClientGuard(True),BlacklistClientGuard)
    @BaseHTTPRessource.HTTPRoute('/me/',methods=[HTTPMethod.GET])
    async def me(self,request:Request,response:Response,client:Annotated[ClientMiniService,Depends(get_client_from_info)],profile:str=Depends(get_client_from_info),authPermission:AuthPermission=Depends(get_auth_permission),clientInfo:ClientAccessInfo=Depends(get_client_info)):

        info = client.client.to_json
        policies = client.authPermission

        return {'client':info,'policies':policies}


    @Throttle(normal=(300,30))
    @UsePermission(UserPermission)
    @UseHandler(MiniServiceHandler)
    @UseLimiter('1/hour',key_func='client')
    @UseInterceptor(InvalidBlacklistTokenInterceptor)
    @UsePipe(ObjectRelationalFriendlyPipe,before=False)
    @UsePipe(MiniServiceInjectorPipe(AdminService,'client'))
    @LockService(VaultService,SettingService,AdminService,as_manager=True,lockType='reader',miniLockType='reader')
    @UseGuard(ClientAuthTypeGuard(accept_access=True, accept_api=False), AuthenticationClientGuard(True),BlacklistClientGuard)
    @BaseHTTPRessource.HTTPRoute('/me/',methods=[HTTPMethod.PUT])
    async def update_myself(self,request:Request,response:Response,updateClient:UpdateClientModel,broker:Annotated[Broker,Depends(Broker)],client:Annotated[ClientMiniService,Depends(get_client_from_info)],profile:str=Depends(get_client_from_info),authPermission:AuthPermission=Depends(get_auth_permission),clientInfo:ClientAccessInfo=Depends(get_client_info)):
        if clientInfo['client_type'] != ClientType.Admin:
            updateClient.issued_for = None
            updateClient.client_scope = None
            updateClient.client_description = None

        updateClient.policies = None
        return await ClientRessource.update_client(request,response,updateClient,broker,client,None)
    
    def verify_client(self, username:str, clientORM:ClientORM,authenticated_flag:bool):
        if clientORM == None:
            raise ClientDoesNotExistError(username)
        
        if clientORM.auth_type != AuthType.ACCESS_TOKEN:
            raise ClientDoesNotExistError(username)

        if clientORM.authenticated == authenticated_flag:
            raise ClientAuthenticationFlagError(username,authenticated_flag)
