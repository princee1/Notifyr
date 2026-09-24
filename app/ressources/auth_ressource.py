from typing import Annotated, Any, Callable, get_args
from typing_extensions import Literal
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette import status
from app.classes.auth_permission import AccessModel, AuthPermission, AuthSignature, AuthState, AuthType, ClientAccessInfo, ClientRefresh, ClientType, Credentials, EncryptedRecoveryTokens, RecoveryTokenGenerator, RecoveryTokens, Role
from app.container import InjectInMethod, Get
from app.decorators.guards import BlacklistClientGuard, ClientAuthTypeGuard, PrimarySessionGuard
from app.decorators.handlers import ClientHandler, MiniServiceHandler, ORMCacheHandler, RedisHandler, ClientSecurityHandler, VaultHandler
from app.decorators.interceptors import InvalidBlacklistTokenInterceptor
from app.decorators.permissions import JWTRouteHTTPPermission, UserPermission
from app.decorators.pipes import AccessTokenModelPipe, MiniServiceInjectorPipe, ObjectRelationalFriendlyPipe, SanitizePathParameterPipe, auth_state_pipe, refresh_logout_handler
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, LockService, PingService, Throttle, UseGuard, UseHandler, UseInterceptor, UseLimiter, UsePermission, UsePipe, UseRoles
from app.definition._service import MiniStateProtocol
from app.depends.dependencies import get_auth_permission, get_client_info, get_client_ip, get_query_params, get_user_agent
from app.depends.funcs_dep import get_client_from_info
from app.depends.variables import ScopeMode, SourceMode, _wrap_checker, source_mode_query,scope_mode_query
from app.errors.depends_error import DataSourceNotSupportedError
from app.errors.security_error import ClientAuthenticationFlagError, ClientDoesNotExistError, ClientNotAllowedToLoginError, PrimarySessionNotValidatedError, SessionNotValidatedError, TokenExpiredError
from app.manager.broker_manager import Broker
from app.manager.session_manager import AuthSessionManager
from app.models.orm.security_model import ClientORM, UpdateClientModel
from app.ressources.admin_ressource import ClientRessource
from app.services.admin_service import VALID_SYNC_MECHANISM, AdminService, ClientMiniService, ClientVaultPath
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from app.services.database.tortoise_service import SECURITY_CREDS, TortoiseConnectionService
from app.services.security_service import JWTAuthService
from app.services.setting_service import SettingService
from app.services.vault_service import VaultService
from tortoise.expressions import Q

SessionMode = Literal['public','private']
session_choices = get_args(SessionMode)

@PingService([VaultService])
@UseHandler(VaultHandler,ClientHandler)
@HTTPRessource('auth')
class AuthRessource(BaseHTTPRessource):

    session_mode_query:Callable[[Request],SessionMode] = get_query_params('session','private',False,raise_except=True,checker=_wrap_checker('scope',lambda v: v in session_choices,choices=session_choices)) 

    @InjectInMethod()
    def __init__(self,tortoiseService:TortoiseConnectionService,adminService:AdminService,settingService:SettingService,vaultService:VaultService,configService:ConfigService):
        super().__init__(None,None)

        self.tortoiseService = tortoiseService
        self.settingService = settingService
        self.adminService = adminService
        self.vaultService = vaultService
        self.configService = configService

        self.blacklist_guard = BlacklistClientGuard()
        self.access_token_pipe = AccessTokenModelPipe()

    @Throttle(normal=(300,30))
    @UseHandler(MiniServiceHandler)
    @UseLimiter('2/day',key_func='client')
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @UsePermission(JWTRouteHTTPPermission,UserPermission)
    @UsePipe(MiniServiceInjectorPipe(AdminService,'client'))
    @LockService(VaultService,AdminService,as_manager=True,lockType='reader',miniLockType='reader')
    @UseGuard(ClientAuthTypeGuard(accept_access=True, accept_api=False),BlacklistClientGuard)
    @BaseHTTPRessource.HTTPRoute('/recover/',methods=[HTTPMethod.GET])
    async def get_recovery_token(self,request:Request,response:Response,client:Annotated[ClientMiniService,Depends(get_client_from_info)],profile:str=Depends(get_client_from_info),authPermission:AuthPermission=Depends(get_auth_permission),clientInfo:ClientAccessInfo=Depends(get_client_info)):

        tokens = []
        recovery = RecoveryTokenGenerator(count=4,part=3)
        async for token in recovery.generate():
            encrypted_code,salt = await client.encrypt_password(token)
            tokens.append(Credentials(password=encrypted_code,salt=salt))

        encrypted_token = EncryptedRecoveryTokens(tokens=tokens,recovery_id=recovery.id)
        await client.create_recovery_code(encrypted_token)

        return recovery.export()

    @Throttle(normal=(300,30))
    @UseLimiter('5/day',key_func='ip')
    @UsePipe(auth_state_pipe,before=False)
    @PingService([TortoiseConnectionService])
    @LockService(TortoiseConnectionService,lockType='reader')
    @LockService(VaultService,SettingService,JWTAuthService,RedisService,lockType='reader')
    @UseHandler(ORMCacheHandler,MiniServiceHandler,ClientSecurityHandler,RedisHandler,ClientHandler)
    @BaseHTTPRessource.HTTPRoute('/recover/',methods=[HTTPMethod.POST],response_class = AccessModel)
    async def recover(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)], credentials: Annotated[HTTPBasicCredentials, Depends(HTTPBasic())],session:Annotated[AuthSessionManager,Depends(AuthSessionManager)]):
        
        clientORM = await ClientORM.filter(Q(client_username=credentials.username) | Q(client_email=credentials.username)).first()
        self.verify_client(credentials.username, clientORM, True)
        
        origin = get_client_ip(request)
        user_agent = get_user_agent(request)

        session_id = session.is_client_authenticated(clientORM)
        session.logout()

        async with self.adminService.lock('reader',str(clientORM.client_id)) as client:
            async with self.tortoiseService.transaction(SECURITY_CREDS) as ctx:

                await self.blacklist_guard.guard(client,None,session_id if session_id else '')
                client.verify_client_origin(origin)

                await client.verify_recovery_code(credentials.password)
                await client.verify_login_count(session_id)

                authSignature,session_id = await client.upsert_session(session_id,origin,user_agent)
                auth_token,refresh_token = await client.generate_access(session_id,authSignature.get('signature',None),ctx=ctx)

                await client.create_recovery_code({})
                session.login(refresh_token)

        if self.configService.SESSION_MECHANISM in VALID_SYNC_MECHANISM:
            broker.propagate(MiniStateProtocol(service=AdminService,to_build=True,id=client.miniService_id  ))

        return self.access_token_pipe.pipe(auth_token,client)

    @Throttle(uniform=(100,250))
    @UseLimiter('5/day',key_func='ip')
    @UseHandler(refresh_logout_handler)
    @UsePipe(auth_state_pipe,before=False)
    @PingService([TortoiseConnectionService])
    @UseHandler(ORMCacheHandler,MiniServiceHandler,ClientSecurityHandler,RedisHandler,ClientHandler)
    @LockService(VaultService,SettingService,JWTAuthService,TortoiseConnectionService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/refresh/',methods=[HTTPMethod.PUT],response_class=AccessModel)
    async def refresh(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],session:Annotated[AuthSessionManager,Depends(AuthSessionManager)]):
        session.logout()
        refreshPermission:ClientRefresh =  session.verify_refresh_token(True)
        
        clientORM = await ClientORM.filter(client_id=refreshPermission['client_id']).first()
        self.verify_client(refreshPermission['client_id'], clientORM)
        origin = get_client_ip(request)

        res = None
        async with self.adminService.lock('reader',str(clientORM.client_id)) as client:
            async with self.tortoiseService.transaction(SECURITY_CREDS) as ctx:
                
                if refreshPermission['status'] == 'active':
                    await self.blacklist_guard.guard(client,None,refreshPermission['session_id'])
                    client.verify_client_origin(origin)
                    await client.verify_refresh_token(refreshPermission)

                    new_signature,_ = await client.upsert_session(refreshPermission['session_id'])
                    auth_token,refresh_token = await client.generate_access(refreshPermission['session_id'],new_signature.get('signature',None),ctx=ctx)

                    session.login(refresh_token)
                    session.update_auth_state(AuthState.AUTH_BY_REFRESH)
                    res = self.access_token_pipe.pipe(auth_token,client)
                else:
                    await client.verify_refresh_token(refreshPermission)
                    new_signature = await client.revoke_itself(ctx,session_id=refreshPermission['session_id'])
                    response.status_code = status.HTTP_204_NO_CONTENT
                    session.update_auth_state(AuthState.LOGOUT_BY_REFRESH)

        if self.configService.SESSION_MECHANISM in VALID_SYNC_MECHANISM:
            broker.propagate(MiniStateProtocol(service=AdminService,to_build=True,id=client.miniService_id  ))
        return res

    @Throttle(normal=(200,70))
    @UseLimiter('5/day',key_func='ip')
    @UsePipe(auth_state_pipe,before=False)
    @PingService([TortoiseConnectionService])
    @LockService(TortoiseConnectionService,lockType='reader')
    @LockService(VaultService,SettingService,JWTAuthService,RedisService,lockType='reader')
    @UseHandler(ORMCacheHandler,MiniServiceHandler,ClientSecurityHandler,RedisHandler,ClientHandler)
    @BaseHTTPRessource.HTTPRoute('/login/',methods=[HTTPMethod.POST],response_class=AccessModel)
    async def login(self,broker:Annotated[Broker,Depends(Broker)],request:Request,response:Response, credentials: Annotated[HTTPBasicCredentials, Depends(HTTPBasic())],session:Annotated[AuthSessionManager,Depends(AuthSessionManager)],mode:SessionMode=Depends(session_mode_query),):

        clientORM = await ClientORM.filter(Q(client_username=credentials.username) | Q(client_email=credentials.username)).first()
        self.verify_client(credentials.username, clientORM, True)

        origin = get_client_ip(request)
        user_agent = get_user_agent(request)

        session_id = session.is_client_authenticated(clientORM)
        session.logout()

        async with self.adminService.lock('reader',str(clientORM.client_id)) as client:
            async with self.tortoiseService.transaction(SECURITY_CREDS) as ctx:
                    
                await self.blacklist_guard.guard(client,None,session_id if session_id else '')
                client.verify_client_origin(origin)

                encryptedPassword = await client.fetch_password()
                await client.compare_password(credentials.password,encryptedPassword)

                await client.verify_login_count(session_id)
                authSignature,session_id = await client.upsert_session(session_id,origin,user_agent)
                auth_token,refresh_token = await client.generate_access(session_id,authSignature.get('signature',None),ctx=ctx)
                
                if mode == 'private':
                    session.login(refresh_token)
        
        if self.configService.SESSION_MECHANISM in VALID_SYNC_MECHANISM:
            broker.propagate(MiniStateProtocol(service=AdminService,to_build=True,id=client.miniService_id  ))

        return self.access_token_pipe.pipe(auth_token,client)

    @Throttle(uniform=(150,200))
    @UsePipe(auth_state_pipe,before=False)
    @UseLimiter('10/day',key_func='client')
    @PingService([TortoiseConnectionService])
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @UseInterceptor(InvalidBlacklistTokenInterceptor)
    @UsePipe(MiniServiceInjectorPipe(AdminService,'client'))
    @UsePermission(JWTRouteHTTPPermission(True),UserPermission)
    @UseGuard(ClientAuthTypeGuard(accept_access=True, accept_api=False))
    @LockService(VaultService,TortoiseConnectionService,AdminService,as_manager=True)
    @UseHandler(ORMCacheHandler,MiniServiceHandler,ClientSecurityHandler,RedisHandler)
    @BaseHTTPRessource.HTTPRoute('/logout/',methods=[HTTPMethod.DELETE])
    async def logout(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],client:Annotated[ClientMiniService,Depends(get_client_from_info)],session:Annotated[AuthSessionManager,Depends(AuthSessionManager)],profile:str=Depends(get_client_from_info),scope:ScopeMode = Depends(scope_mode_query),authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):

        async with self.tortoiseService.transaction(SECURITY_CREDS) as ctx:
            if scope == 'single':
                await client.revoke_itself(ctx,clientInfo['session_id'])
            else:
                session.verify_refresh_token(False)
                if not await client.is_primary_session(clientInfo['session_id']):
                    raise PrimarySessionNotValidatedError(clientInfo['client_id'],clientInfo['session_id'])
                
                await client.revoke_itself(ctx)

            request.state.clear = True
            session.logout()

        if self.configService.SESSION_MECHANISM in VALID_SYNC_MECHANISM:
            broker.propagate(MiniStateProtocol(service=AdminService,to_build=True,id=client.miniService_id  ))

        return

    @Throttle(normal=(250,50))
    @UseHandler(MiniServiceHandler)
    @UseLimiter('20/day',key_func='client')
    @UsePermission(JWTRouteHTTPPermission,UserPermission)
    @UsePipe(MiniServiceInjectorPipe(AdminService,'client'))
    @LockService(AdminService,as_manager=True,lockType='reader',miniLockType='reader')
    @UseGuard(ClientAuthTypeGuard(accept_access=True, accept_api=False),BlacklistClientGuard)
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
    @UseGuard(ClientAuthTypeGuard(accept_access=True, accept_api=False),BlacklistClientGuard)
    @LockService(VaultService,SettingService,AdminService,as_manager=True,lockType='reader',miniLockType='reader')
    @BaseHTTPRessource.HTTPRoute('/me/',methods=[HTTPMethod.PUT])
    async def update_myself(self,request:Request,response:Response,updateClient:UpdateClientModel,broker:Annotated[Broker,Depends(Broker)],client:Annotated[ClientMiniService,Depends(get_client_from_info)],profile:str=Depends(get_client_from_info),authPermission:AuthPermission=Depends(get_auth_permission),clientInfo:ClientAccessInfo=Depends(get_client_info)):
        if clientInfo['client_type'] != ClientType.Admin:
            updateClient.issued_for = None
            updateClient.client_scope = None
            updateClient.client_description = None

        updateClient.policies = None
        return await ClientRessource.update_client(request,response,updateClient,broker,client,None,authPermission,clientInfo)

    if Get(ConfigService).SESSION_MECHANISM != 'none':

        @UseRoles([Role.ADMIN])
        @UsePipe(SanitizePathParameterPipe({},session=True))
        @UsePermission(JWTRouteHTTPPermission,UserPermission)
        @UsePipe(MiniServiceInjectorPipe(AdminService,'client'))
        @LockService(VaultService,SettingService,lockType='reader')
        @UseHandler(MiniServiceHandler,ClientSecurityHandler,ClientHandler)
        @UseGuard(ClientAuthTypeGuard(accept_access=True, accept_api=False),BlacklistClientGuard,PrimarySessionGuard)
        @BaseHTTPRessource.HTTPRoute('/session/{session_id:path}',methods=[HTTPMethod.GET])
        async def fetch_session(self,request:Request,response:Response,client:Annotated[ClientMiniService,Depends(get_client_info)],session_id:str='',source:SourceMode=Depends(source_mode_query),profile:str=Depends(get_client_from_info),clientInfo:ClientAccessInfo=Depends(get_client_info),authPermission:AuthPermission=Depends(get_auth_permission)):
            res = {}
            match source:
                case 'database':
                    if session_id == '':
                        path = f"clients/{ClientVaultPath.SESSIONS_VAULT_PATH(client.client_id,'')}"
                        sessions = self.vaultService.security_engine.list(path)
                        for s in sessions:
                            p =  ClientVaultPath.SESSIONS_VAULT_PATH(client.client_id,s)
                            res[s] = self.vaultService.security_engine.read('clients',p)
                        return res
                    else:
                        p =  ClientVaultPath.SESSIONS_VAULT_PATH(client.client_id,s)
                        res[s] = self.vaultService.security_engine.read('clients',p)
                case 'memory':
                    async with client.lock('reader'):
                        if session_id == '':
                            for s in client.sessions.keys():
                                res[s] = client.sessions[s].to_plain()
                        else:
                            if session_id not in client.sessions:
                                raise SessionNotValidatedError(client.client_id,session_id)

                            res[session_id] = client.sessions[session_id].to_plain()
                case _:
                    raise DataSourceNotSupportedError(source,['database','memory'])

            return res

        @UseRoles([Role.ADMIN])
        @UseInterceptor(InvalidBlacklistTokenInterceptor)
        @UsePipe(SanitizePathParameterPipe({},session=True))
        @UsePermission(JWTRouteHTTPPermission,UserPermission)
        @UsePipe(MiniServiceInjectorPipe(AdminService,'client'))
        @UseHandler(MiniServiceHandler,ClientSecurityHandler,ClientHandler)
        @UseGuard(ClientAuthTypeGuard(accept_access=True, accept_api=False),BlacklistClientGuard,PrimarySessionGuard(True))
        @LockService(VaultService,SettingService,AdminService,as_manager=True,lockType='reader',miniLockType='reader')
        @BaseHTTPRessource.HTTPRoute('/session/{session_id:path}',methods=[HTTPMethod.DELETE])
        async def delete_session(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],session:Annotated[AuthSessionManager,Depends(AuthSessionManager)],client:Annotated[ClientMiniService,Depends(get_client_info)],session_id:str='',profile:str=Depends(get_client_from_info),clientInfo:ClientAccessInfo=Depends(get_client_info),authPermission:AuthPermission=Depends(get_auth_permission)):
            res = None
            if session_id == '':
                origin = get_client_ip(request)
                user_agent = get_user_agent(request)

                await client.revoke_itself()
                session.update_auth_state(AuthState.SESSION_REVOKED)
                authSignature:AuthSignature = await client.upsert_session(clientInfo['session_id'],origin,user_agent,False)
                access_token,refresh_token = await client.generate_access(clientInfo['session_id'],authSignature.get('signature',None))

                session.update_auth_state(AuthState.SESSION_REFRESHED)
                request.state.clear = True

                session.login(refresh_token)
                
                res = self.access_token_pipe.pipe(access_token,client)

            else:
                await client.revoke_itself(session_id=session_id)
                response.status_code = status.HTTP_204_NO_CONTENT

            if self.configService.SESSION_MECHANISM in VALID_SYNC_MECHANISM:
                broker.propagate(MiniStateProtocol(service=AdminService,to_build=True,id=client.miniService_id  ))

            return res


    def verify_client(self,username:str, clientORM:ClientORM,__check_can_login__=False):
        if clientORM == None:
            raise ClientDoesNotExistError(username,True)
        
        if clientORM.auth_type != AuthType.ACCESS_TOKEN:
            raise ClientDoesNotExistError(username)

        if __check_can_login__ and not clientORM.can_login:
            raise ClientNotAllowedToLoginError(username)

    ###############################################################################################################################
    #############################################                                              ####################################
    ###############################################################################################################################


    @BaseHTTPRessource.HTTPRoute('/password-forget/',methods=[HTTPMethod.POST],deprecated=True,mount=False)
    async def password_forgot(self,request:Request,response:Response):
        ...

    @BaseHTTPRessource.HTTPRoute('/password-reset/',methods=[HTTPMethod.POST],deprecated=True, mount=False)
    async def password_reset(self,request:Request,response:Response):
        ...

        