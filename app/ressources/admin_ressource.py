from typing import Annotated, Callable, Optional, get_args
from fastapi import Depends, HTTPException, Query, Request, Response, status
from tortoise.expressions import Q
from app.decorators.guards import AdminModificationGuard,  BlacklistClientGuard, ClientAuthTypeGuard, PolicyGuard, TortoiseHardLimitGuard
from app.decorators.interceptors import DataCostInterceptor, InvalidBlacklistTokenInterceptor
from app.definition._cost import DataCost
from app.definition._service import MiniStateProtocol, StateProtocol
from app.depends.funcs_dep import fetch_group, fetch_policy, get_blacklist, get_group, get_client, get_policy
from app.depends.orm_cache import WILDCARD, BlacklistClientCache, BlacklistGroupCache
from app.depends.variables import SourceMode, _wrap_checker,source_mode_query
from app.errors.depends_error import DataSourceNotSupportedError
from app.manager.broker_manager import Broker
from app.manager.merchant_manager import Merchant
from app.manager.session_manager import AuthSessionManager
from app.models.orm.security_model import BlacklistModel, ClientModel, ClientORM, GroupClientORM, GroupModel, PolicyMappingORM, RevokeSessionModel, UnRevokeGenerationIDModel, UpdateClientModel
from app.services.admin_service import AdminService, ClientMiniService
from app.services.database.tortoise_service import TortoiseConnectionService,SECURITY_CREDS
from app.services.profile_service import ProfileService
from app.services.vault_service import VaultService
from app.services.setting_service import SettingService
from app.services.security_service import JWTAuthService, SecurityService
from app.services.config_service import ConfigService
from app.utils.constant import ConfigAppConstant, CostConstant
from app.depends.dependencies import get_auth_permission, get_client_info, get_client_ip, get_query_params, get_request_id, get_user_agent
from app.container import InjectInMethod, Get
from app.definition._ressource import PingService, UseInterceptor, LockService, UseGuard, UseHandler, UsePermission, BaseHTTPRessource, HTTPMethod, HTTPRessource, UsePipe, UseRoles, UseLimiter,HTTPStatusCode
from app.decorators.permissions import AdminPermission, JWTRouteHTTPPermission
from app.classes.auth_permission import AccessModel, AuthPermission, AuthSignature, AuthType, ClientAccessInfo, ClientType, PoliciesNotMatchingError, PolicyModel, PolicyUpdateMode, Role, Scope
from app.decorators.handlers import AsyncIOHandler, CostHandler, DataSourceHandler, MiniServiceHandler, ORMCacheHandler, PydanticHandler, RedisHandler, ClientHandler, ClientSecurityHandler, ServiceAvailabilityHandler, TortoiseHandler, ValueErrorHandler, VaultHandler
from app.decorators.pipes import  AccessTokenModelPipe, ForceClientPipe, ForceGroupPipe, FunctionInjectorPipe, MiniServiceInjectorPipe, ObjectRelationalFriendlyPipe
from app.utils.helper import  generateId, uuid_v1_mc
from app.utils.toolbox import RunInThreadPool
from app.errors.security_error import ClientAlreadyExistError, IdentityAlreadyBlacklistedError, AuthzSignatureMisMatchError, ClientDoesNotExistError, GroupIdNotMatchError, SecurityIdentityNotResolvedError, SessionNotValidatedError

ADMIN_PREFIX = 'admin'
CLIENT_PREFIX = 'client'

policy_update_mode_query:Callable[[Request],str] = get_query_params('mode','merge',False,raise_except=True,checker=_wrap_checker('mode', lambda v: v in get_args(PolicyUpdateMode), choices=list(get_args(PolicyUpdateMode))))


@UsePermission(JWTRouteHTTPPermission,AdminPermission)
@UseHandler(ServiceAvailabilityHandler,TortoiseHandler,AsyncIOHandler)
@HTTPRessource('policy')
class PolicyRessource(BaseHTTPRessource):
    
    @InjectInMethod()
    def __init__(self,adminService:AdminService,vaultService:VaultService,tortoiseService:TortoiseConnectionService):
        super().__init__()
        self.vaultService = vaultService
        self.adminService = adminService
        self.tortoiseService = tortoiseService

    @UseGuard(PolicyGuard)
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @PingService([VaultService,ProfileService])
    @LockService(VaultService,ProfileService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
    async def create_policy(self,request:Request,response:Response, policyModel:PolicyModel, authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):
        policy_id = generateId(12)
        policy_model = policyModel.model_dump(mode='python')
        self.vaultService.security_engine.put('policies',policy_model,path=policy_id)
        return  {**policy_model, **{'policy_id':policy_id}}

    @UsePipe(FunctionInjectorPipe(fetch_policy,'policy'))
    @PingService([VaultService,TortoiseConnectionService])
    @LockService(VaultService,TortoiseConnectionService,AdminService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/{policy}/',methods=[HTTPMethod.DELETE])
    async def delete_policy(self,broker:Annotated[Broker,Depends(Broker)],request:Request,policy:Annotated[PolicyModel,Depends(get_policy)],authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):

        async with self.tortoiseService.transaction(SECURITY_CREDS,1,lock='none') as ctx:
            await PolicyMappingORM.filter(policy_id=policy).using_db(ctx).delete()
            await RunInThreadPool(self.vaultService.security_engine.delete)('policies',policy._policy_id)

        broker.propagate(StateProtocol(service=AdminService,to_build=True,callback_state_function=AdminService.load_clients.__name__))
        return {**policy.model_dump(), **{'policy_id':policy._policy_id}}

    @UseGuard(PolicyGuard)
    @UseHandler(PydanticHandler)
    @PingService([ProfileService])
    @UsePipe(FunctionInjectorPipe(fetch_policy,'policy'))
    @LockService(ProfileService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/{policy}/',methods=[HTTPMethod.PUT])
    async def update_policy(self,broker:Annotated[Broker,Depends(Broker)],request:Request,policyModel:PolicyModel,policy:Annotated[PolicyModel,Depends(get_policy)],mode:PolicyUpdateMode =Depends(policy_update_mode_query), authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):

        policy.update(policyModel,mode)
        data = policy.model_dump()
        await RunInThreadPool(self.vaultService.security_engine.put)('policies',data,policy._policy_id)
        broker.propagate(StateProtocol(service=AdminService,to_build=True,callback_state_function=AdminService.load_clients.__name__))
        return {**data, **{'policy_id':policy._policy_id}}
        
    @UsePipe(FunctionInjectorPipe(fetch_policy,'policy'))
    @BaseHTTPRessource.HTTPRoute('/{policy}/',methods=[HTTPMethod.GET])
    async def read_policy(self,request:Request,policy:Annotated[PolicyModel,Depends(get_policy)],authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):
        return {**policy.model_dump(), **{'policy_id':policy._policy_id}}


@UsePermission(JWTRouteHTTPPermission)
@PingService([TortoiseConnectionService])
@LockService(TortoiseConnectionService,lockType='reader',infinite_wait=True,check_status=False)
@UseHandler(ServiceAvailabilityHandler,TortoiseHandler,AsyncIOHandler)
@HTTPRessource(CLIENT_PREFIX)
class ClientRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self, configService: ConfigService, securityService: SecurityService, jwtAuthService: JWTAuthService, adminService: AdminService,tortoiseService:TortoiseConnectionService):
        super().__init__()
        self.configService = configService
        self.securityService = securityService
        self.jwtAuthService = jwtAuthService
        self.adminService = adminService
        self.tortoiseService = tortoiseService

        self.settingService = Get(SettingService)
        self.vaultService = Get(VaultService)

        self.key = self.vaultService.CLIENT_PASSWORD_HASH_KEY

    @PingService([VaultService])
    @UsePermission(AdminPermission)
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @UseInterceptor(DataCostInterceptor(CostConstant.CLIENT_CREDIT))
    @LockService(SettingService,VaultService,AdminService,lockType='reader')
    @UseHandler(CostHandler,RedisHandler,VaultHandler,ClientHandler,ClientSecurityHandler)
    @BaseHTTPRessource.Post('/')
    async def create_client(self,broker:Annotated[Broker,Depends(Broker)], merchant:Annotated[Merchant,Depends(Merchant)],cost:Annotated[DataCost,Depends(DataCost)],request:Request,response:Response, clientModel: ClientModel, authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):

        clientORM = await ClientORM.filter(Q(client_username=clientModel.client_username) | Q(client_email=clientModel.client_email)).first()
        if clientORM != None:
            raise ClientAlreadyExistError(clientModel.client_username or clientModel.client_email)
        
        valid_policies = await RunInThreadPool(self.vaultService.security_engine.list)('policies')
        if len((policies_error:=set(clientModel).difference(valid_policies)))>0:
            raise PoliciesNotMatchingError(policies_error)

        client_data = { **clientModel.model_dump(),'client_id':clientModel._client_id}
        await fetch_group(clientModel.group) if clientModel.group != None else None

        async def transaction():
            async with self.tortoiseService.transaction(SECURITY_CREDS) as ctx:
                mapping = [PolicyMappingORM(policy_id=policy_id,client=client,group=None) for policy_id in clientModel.policies]
                clientORM = await ClientORM.create(ctx,**client_data)
                await PolicyMappingORM.bulk_create(mapping,using_db=ctx)
                client = ClientMiniService(self.vaultService,self.configService,self.jwtAuthService,self.securityService,clientORM,[])
                await client.store_password(clientModel.password)

        async def rollback():
            await RunInThreadPool(self.vaultService.secrets_engine.delete)('clients',clientModel._client_id)

        broker.propagate(StateProtocol(service=AdminService,to_build=True,callback_state_function=AdminService.load_clients.__name__))

        return client_data

    @PingService([VaultService])
    @UsePermission(AdminPermission)
    @UseGuard(AdminModificationGuard)
    @UseInterceptor(InvalidBlacklistTokenInterceptor)
    @UsePipe(ObjectRelationalFriendlyPipe,before=False)
    @UsePipe(MiniServiceInjectorPipe(AdminService,'client'))
    @UseHandler(ValueErrorHandler,ORMCacheHandler,VaultHandler,ClientHandler,ClientSecurityHandler,MiniServiceHandler)
    @LockService(VaultService,SettingService,AdminService,as_manager=True,lockType='reader',miniLockType='reader')
    @BaseHTTPRessource.HTTPRoute('/{client}/', methods=[HTTPMethod.PUT])
    async def update_client(self,request:Request,response:Response, updateClient:UpdateClientModel,broker:Annotated[Broker,Depends(Broker)],client: Annotated[ClientMiniService, Depends(get_client)],mode:PolicyUpdateMode = Depends(policy_update_mode_query),profile:str=Depends(get_client), authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info) ):

        if updateClient.client_username:
            clientORM = await ClientORM.filter(Q(client_username=updateClient.client_username)).first()
            if clientORM != None:
                raise ClientAlreadyExistError(updateClient.client_username)

        group = await fetch_group(updateClient.group) if updateClient.group  else None

        async with self.tortoiseService.transaction(SECURITY_CREDS) as ctx:
            is_revoked,password,salt = await client.update_client(updateClient,group,ctx)
            if updateClient.policies != None:
                await self.adminService.update_policy(updateClient.policies,mode,client,group,ctx)
            if is_revoked:
                await client.revoke_itself(ctx)
                request.state.clear = True
            await client.save(ctx)
            if password:
                await client.store_password(password,salt)

        broker.propagate(StateProtocol(service=AdminService,to_build=True,callback_state_function=AdminService.load_clients.__name__))
        return client.client

    @PingService([VaultService])        
    @UsePermission(AdminPermission)
    @UseGuard(AdminModificationGuard)
    @HTTPStatusCode(status.HTTP_200_OK,)
    @UsePipe(ObjectRelationalFriendlyPipe,before=False)
    @UsePipe(MiniServiceInjectorPipe(AdminService,'client'))
    @LockService(SettingService,VaultService,AdminService,as_manager=True,miniLockType='reader')
    @UseInterceptor(DataCostInterceptor(CostConstant.CLIENT_CREDIT,'refund'))
    @UseHandler(ORMCacheHandler,CostHandler,RedisHandler,VaultHandler,ClientSecurityHandler,MiniServiceHandler)
    @BaseHTTPRessource.Delete('/{client}/')
    async def delete_client(self,broker:Annotated[Broker,Depends(Broker)], merchant:Annotated[Merchant,Depends(Merchant)],cost:Annotated[DataCost,Depends(DataCost)],request:Request,response:Response, client: Annotated[ClientMiniService, Depends(get_client)],profile:str=Depends(get_client), authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):
        
        async def transaction():
            async with self.tortoiseService.transaction(SECURITY_CREDS,lock='reader') as ctx:
                await client.delete_itself(ctx)
                await BlacklistClientCache.InvalidAll([client.client_id,WILDCARD])

        merchant.safe_payment(
            None,
            None,
            transaction
        )
        broker.propagate(StateProtocol(service=AdminService,to_build=True,callback_state_function=AdminService.load_clients.__name__))
        return client.client
    
    @UsePermission(AdminPermission)
    @LockService(AdminService,lockType='reader')
    @UseHandler(MiniServiceHandler,DataSourceHandler)
    @UsePipe(ObjectRelationalFriendlyPipe,before=False)
    @BaseHTTPRessource.Get('/{client:path}')
    async def read_client(self,request:Request,response:Response,client:str='',source:SourceMode=Depends(source_mode_query),authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):
        match source:
            case 'database':
                if client == '':
                    return [ c for c in await ClientORM.all() if c.client_type!=ClientType.Admin]
                else:
                    return await ClientORM.filter(client_id=client)
            case 'memory':
                if client != '':
                    async with self.adminService.MiniServiceStore.lock(client) as service:
                        return service.client
                else:
                    clients = []
                    async for c in self.adminService.MiniServiceStore.aiter(predicate=lambda c:c.client.client_type!=ClientType.Admin):
                        clients.append(c.client)
                    return clients
            case _:
                raise DataSourceNotSupportedError(source,['database','memory'])

    @PingService([VaultService])
    @UsePermission(AdminPermission)
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @LockService(VaultService,lockType='reader')
    @UseHandler(ClientSecurityHandler,VaultHandler)
    @UsePipe(ObjectRelationalFriendlyPipe,before=False)
    @UseGuard(TortoiseHardLimitGuard(10,GroupClientORM))
    @BaseHTTPRessource.Post('/group/')
    async def create_group(self, groupModel: GroupModel,request:Request,response:Response, authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):

        valid_policies = await RunInThreadPool(self.vaultService.security_engine.list)('policies')
        if len((policies_error:=set(groupModel.policies).difference(valid_policies)))>0:
            raise PoliciesNotMatchingError(policies_error)

        async with self.tortoiseService.transaction(SECURITY_CREDS) as ctx:    
            group:GroupClientORM = await GroupClientORM.create(ctx,group_name=groupModel.group_name)
            await PolicyMappingORM.bulk_create([PolicyMappingORM(policy_id=policy_id,client=None,group=group) for policy_id in groupModel.policies],using_db=ctx)

        return group

    @UseHandler(ORMCacheHandler)
    @UsePermission(AdminPermission)
    @LockService(AdminService,lockType='reader')
    @UsePipe(FunctionInjectorPipe(fetch_group,'group'))
    @UsePipe(ObjectRelationalFriendlyPipe,before=False)
    @BaseHTTPRessource.Delete('/group/{group}/')
    async def delete_group(self,broker:Annotated[Broker,Depends(Broker)],request:Request,response:Response, group: Annotated[GroupClientORM, Depends(get_group)], authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):

        async with self.tortoiseService.transaction(SECURITY_CREDS) as ctx:
            await group.delete(ctx)
            await BlacklistGroupCache.InvalidAll([group.group_id,WILDCARD])

        broker.propagate(StateProtocol(service=AdminService,to_build=True,callback_state_function=AdminService.load_clients.__name__))

        return group

    @UsePermission(AdminPermission)
    @UsePipe(ObjectRelationalFriendlyPipe,before=False)
    @BaseHTTPRessource.Get('/group/{group:path}')
    async def read_group(self,request:Request,response:Response,group:str='',authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):
        if group == '':
            return await GroupClientORM.all()
        else:
            return await fetch_group(group)
        
@UseHandler(ServiceAvailabilityHandler)
@PingService([TortoiseConnectionService])
@UsePermission(JWTRouteHTTPPermission,AdminPermission)
@UseHandler(TortoiseHandler,AsyncIOHandler,RedisHandler)
@LockService(TortoiseConnectionService,lockType='reader',infinite_wait=True,check_status=False)
@HTTPRessource(ADMIN_PREFIX, routers=[ClientRessource,PolicyRessource])
class AdminRessource(BaseHTTPRessource):

    clear_cache_query = get_query_params('clear','false',parse=True,raise_except=True)
    admin_disconnect_query = get_query_params('admin','true',parse=True,raise_except=True)

    @InjectInMethod()
    def __init__(self, configService: ConfigService, jwtAuthService: JWTAuthService, securityService: SecurityService,tortoiseService:TortoiseConnectionService,vaultService:VaultService,adminService:AdminService):
        BaseHTTPRessource.__init__(self)
        self.configService = configService
        self.jwtService = jwtAuthService
        self.securityService = securityService
        self.tortoiseService = tortoiseService
        self.vaultService = vaultService
        self.adminService = adminService

    @PingService([VaultService])
    @UseLimiter(limit_value='20/week')
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @LockService(VaultService,JWTAuthService,lockType='reader')
    @UseHandler(ClientHandler,ORMCacheHandler,RedisHandler,ClientSecurityHandler)
    @BaseHTTPRessource.HTTPRoute('/blacklist/', methods=[HTTPMethod.POST])
    async def blacklist_tokens(self,blacklist:BlacklistModel, response:Response, request: Request,authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):
        
        match blacklist.mode:
            case 'session':
                client_id,session = blacklist.identity.split('@')
                                
                client = await ClientORM.filter(client_id=client_id).first()
                if client == None or client.client_type == ClientType.Admin:
                    raise ClientDoesNotExistError(client_id)

                if await BlacklistClientCache.Get([client.client_id,session]) and not blacklist.force:
                    raise IdentityAlreadyBlacklistedError(blacklist.identity,'session')

                path = f"/clients/{client.client_id}/auth-signature"
                sessions:list[str] = await RunInThreadPool(self.vaultService.security_engine.list)(path)

                if session not in sessions:
                    raise SessionNotValidatedError(client_id,session)
                await BlacklistGroupCache.Store([client_id,session],True,blacklist.time)
                
            case 'client':
                if await BlacklistClientCache.Get([blacklist.identity,'']) and not blacklist.force:
                    raise IdentityAlreadyBlacklistedError(blacklist.identity,'client')

                client = await ClientORM.filter(client_id=blacklist.identity).first()
                if client == None or client.client_type == ClientType.Admin:
                    raise ClientDoesNotExistError(blacklist.identity)

                await BlacklistGroupCache.Store([blacklist.identity,''],True,blacklist.time)

            case 'group':
                if await BlacklistGroupCache.Get([blacklist.identity]) and not blacklist.force:
                    raise IdentityAlreadyBlacklistedError(blacklist.identity,'group')
                
                await fetch_group(blacklist.identity)                
                await BlacklistGroupCache.Store(blacklist.identity,True,blacklist.time)

    @UseLimiter(limit_value='20/week')
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @UseHandler(ClientHandler,ORMCacheHandler,ClientSecurityHandler,RedisHandler)
    @BaseHTTPRessource.HTTPRoute('/blacklist/', methods=[HTTPMethod.DELETE])
    async def un_blacklist_tokens(self, blacklist:BlacklistModel,response:Response, request: Request, authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):

        match blacklist.mode:
            case 'session':
                client_id,session = blacklist.identity.split('@')

                if not await BlacklistClientCache.Get([client_id,session]):
                    raise IdentityAlreadyBlacklistedError(blacklist.identity,blacklist.mode,reversed_=True)
                
                await BlacklistClientCache.Invalid([client_id,session])
            case 'client':
                if not await BlacklistClientCache.Get([blacklist.identity,'']):
                    raise IdentityAlreadyBlacklistedError(blacklist.identity,blacklist.mode,reversed_=True)
                
                await BlacklistClientCache.Invalid([blacklist.identity,''])
            case 'group':
                if not await BlacklistGroupCache.Get(blacklist.identity):
                    raise IdentityAlreadyBlacklistedError(blacklist.identity,blacklist.mode,reversed_=True)

                await BlacklistGroupCache.Invalid(blacklist.identity)

    
    @UseLimiter(limit_value='10/day')
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @UseInterceptor(InvalidBlacklistTokenInterceptor)
    @UseGuard(AdminModificationGuard,ClientAuthTypeGuard(),)
    @UsePipe(MiniServiceInjectorPipe(AdminService,'client'))
    @PingService([VaultService,AdminService],is_manager=True)
    @UseHandler(ClientHandler,ORMCacheHandler,VaultHandler,MiniServiceHandler,ClientSecurityHandler)
    @LockService(VaultService,SettingService,AdminService,JWTAuthService,lockType='reader',as_manager=True)
    @BaseHTTPRessource.HTTPRoute('/revoke/{client}/', methods=[HTTPMethod.DELETE])
    async def revoke_tokens(self,revoke:RevokeSessionModel,broker:Annotated[Broker,Depends(Broker)], request: Request,response:Response, client: Annotated[ClientMiniService, Depends(get_client)],profile:str=Depends(get_client), authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):

        async with self.tortoiseService.transaction(SECURITY_CREDS) as ctx:    
            if client.client.auth_type == AuthType.ACCESS_TOKEN:
                await client.revoke_itself(ctx,revoke.session,revoke.can_login)
                if not revoke.session:
                    request.state.clear = True
                else:
                    await BlacklistClientCache.Invalid([client.client_id,revoke.session])
            else:
                await client.revoke_itself(ctx)
                request.state.clear = True

        broker.propagate(MiniStateProtocol(service=AdminService,to_build=True,id=client.miniService_id ))
        return
        
    @UseLimiter(limit_value='4/day')
    @UsePipe(AccessTokenModelPipe,before=False)
    @UsePipe(MiniServiceInjectorPipe(AdminService,'client'))
    @PingService([VaultService,AdminService],is_manager=True)
    @UseHandler(ClientHandler,ORMCacheHandler,MiniServiceHandler)
    @LockService(VaultService,SettingService,AdminService,lockType='reader',as_manager=True)
    @UseGuard(AdminModificationGuard,BlacklistClientGuard,ClientAuthTypeGuard(accept_access=False, accept_api=True),)
    @BaseHTTPRessource.HTTPRoute('/issue-auth/{client}/', methods=[HTTPMethod.GET],response_model=AccessModel)
    async def issue_auth_token(self,broker:Annotated[Broker,Depends(Broker)], client: Annotated[ClientMiniService, Depends(get_client)], request: Request, response:Response ,profile:str= Depends(get_client),authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):
        
        async with self.tortoiseService.transaction(SECURITY_CREDS) as ctx:    
            await client.revoke_itself(ctx)
            session_id = str(uuid_v1_mc())
            authSignature:AuthSignature = await client.upsert_session(session_id,_check_=False)
            api_token,_ = await client.generate_access(session_id,authSignature['signature'])
            
        broker.propagate(MiniStateProtocol(service=AdminService,to_build=True,id=client.miniService_id  ))
        return api_token
        
    #######################################################################################################################################
    ###############                                                                                                     ###################
    ###############                                                                                                     ###################
    ###################################                                                  ##################################################
    ###############                                                                                                     ###################
    ###############                                                                                                     ###################
    #######################################################################################################################################
    
    @PingService([VaultService])
    @UseLimiter(limit_value='1/day')
    @UsePipe(AccessTokenModelPipe(accept_none=True),before=False)
    @UseHandler(ClientHandler,ORMCacheHandler,VaultHandler,ClientSecurityHandler)
    @LockService(VaultService,SettingService,AdminService,JWTAuthService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/revoke/', methods=[HTTPMethod.POST],deprecated=True,mount=False,response_class=AccessModel)
    async def revoke_all_tokens(self, request: Request,response:Response, session:Annotated[AuthSessionManager,Depends(AuthSessionManager)],broker:Annotated[Broker,Depends(Broker)],unRevokeModel:Optional[UnRevokeGenerationIDModel]=None,admin:bool=Depends(admin_disconnect_query),clear:bool=Depends(clear_cache_query), authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):   
        
        async with self.tortoiseService.transaction(SECURITY_CREDS) as ctx:
            await self.adminService.disconnect_all(admin,ctx=ctx)
            if unRevokeModel:
                await self.adminService.unrevoke_all_tokens(**unRevokeModel.model_dump())
            else:
                await self.adminService.revoke_all_tokens()

        if clear: await BlacklistGroupCache.InvalidAll([WILDCARD])
        broker.propagate(StateProtocol(service=self.jwtService.name,to_build=True,bypass_async_verify=True,force_sync_verify=True))

        if admin: return
        async with self.adminService.lock('reader',clientInfo['client_id']) as client:
            origin = get_client_ip(request)
            user_agent = get_user_agent(request)

            authSignature:AuthSignature = await client.upsert_session(clientInfo['session_id'],origin,user_agent,_check_=False)
            access_token,refresh_token = client.generate_access(clientInfo['session_id'],authSignature['signature'])
            session.login(refresh_token)

        return access_token
    
    @UseLimiter(limit_value='1/day')
    @PingService([VaultService])
    @LockService(VaultService,JWTAuthService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/revoke-version/', methods=[HTTPMethod.GET],deprecated=True,mount=False)
    def check_version(self,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info)):
        return self.jwtService.GENERATION_METADATA


