from random import randint
import time
from typing import Annotated, Callable, get_args
from fastapi import Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from app.decorators.guards import AuthenticatedClientGuard, BlacklistClientGuard, PolicyGuard, TortoiseHardLimitGuard
from app.decorators.interceptors import DataCostInterceptor
from app.definition._cost import DataCost
from app.definition._service import StateProtocol
from app.depends.funcs_dep import fetch_group, fetch_policy, get_blacklist, get_group, get_client, get_policy
from app.depends.orm_cache import WILDCARD, BlacklistORMCache
from app.depends.variables import SourceMode, _wrap_checker,source_mode_query
from app.errors.depends_error import DataSourceNotSupportedError
from app.interface.issue_auth import IssueAuthInterface
from app.manager.broker_manager import Broker
from app.manager.merchant_manager import Merchant
from app.models.orm.security_model import BlacklistModel, ClientModel, ClientORM, GroupClientORM, GroupModel, PolicyMappingORM, UpdateClientModel, raw_revoke_challenges
from app.services.admin_service import AdminService, AuthSignature, ClientMiniService
from app.services.database.tortoise_service import TortoiseConnectionService,SECURITY_CREDS
from app.services.profile_service import ProfileService
from app.services.vault_service import VaultService
from app.services.setting_service import SettingService
from app.services.security_service import JWTAuthService, SecurityService
from app.services.config_service import ConfigService
from app.utils.constant import ConfigAppConstant, CostConstant
from app.depends.dependencies import get_auth_permission, get_query_params, get_request_id
from app.container import InjectInMethod, Get
from app.definition._ressource import PingService, UseInterceptor, LockService, UseGuard, UseHandler, UsePermission, BaseHTTPRessource, HTTPMethod, HTTPRessource, UsePipe, UseRoles, UseLimiter,HTTPStatusCode
from app.decorators.permissions import AdminPermission, JWTRouteHTTPPermission
from app.classes.auth_permission import AuthPermission, AuthType, ClientType, PoliciesNotMatchingError, PolicyModel, PolicyUpdateMode, Role, Scope
from app.decorators.handlers import AsyncIOHandler, CostHandler, DataSourceHandler, MiniServiceHandler, ORMCacheHandler, PydanticHandler, RedisHandler, AuthClientHandler, SecurityHandler, ServiceAvailabilityHandler, TortoiseHandler, ValueErrorHandler, VaultHandler
from app.decorators.pipes import  ForceClientPipe, ForceGroupPipe, FunctionInjectorPipe, MiniServiceInjectorPipe, ObjectRelationalFriendlyPipe
from app.utils.helper import  generateId
from app.utils.toolbox import RunInThreadPool
from app.errors.security_error import IdentityAlreadyBlacklistedError, AuthzSignatureMisMatchError, ClientDoesNotExistError, GroupIdNotMatchError, SecurityIdentityNotResolvedError

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
    async def create_policy(self,request:Request,response:Response, policyModel:PolicyModel, authPermission:AuthPermission=Depends(get_auth_permission)):
        policy_id = generateId(12)
        policy_model = policyModel.model_dump(mode='python')
        self.vaultService.security_engine.put('policies',policy_model,path=policy_id)
        return  {**policy_model, **{'policy_id':policy_id}}

    @UsePipe(FunctionInjectorPipe(fetch_policy,'policy'))
    @PingService([VaultService,TortoiseConnectionService])
    @LockService(VaultService,TortoiseConnectionService,AdminService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/{policy}/',methods=[HTTPMethod.DELETE])
    async def delete_policy(self,broker:Annotated[Broker,Depends(Broker)],request:Request,policy:Annotated[PolicyModel,Depends(get_policy)],authPermission:AuthPermission=Depends(get_auth_permission)):

        async with self.tortoiseService.transaction(SECURITY_CREDS,1,lock='none') as ctx:
            await PolicyMappingORM.filter(policy_id=policy).using_db(ctx).delete()
            await RunInThreadPool(self.vaultService.security_engine.delete)('policies',policy._policy_id)

        broker.propagate(StateProtocol(service=AdminService))
        return {**policy.model_dump(), **{'policy_id':policy._policy_id}}

    @UseGuard(PolicyGuard)
    @UseHandler(PydanticHandler)
    @PingService([ProfileService])
    @UsePipe(FunctionInjectorPipe(fetch_policy,'policy'))
    @LockService(ProfileService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/{policy}/',methods=[HTTPMethod.PUT])
    async def update_policy(self,broker:Annotated[Broker,Depends(Broker)],request:Request,policyModel:PolicyModel,policy:Annotated[PolicyModel,Depends(get_policy)],mode:PolicyUpdateMode =Depends(policy_update_mode_query), authPermission:AuthPermission=Depends(get_auth_permission)):

        policy.update(policyModel,mode)
        data = policy.model_dump()
        await RunInThreadPool(self.vaultService.security_engine.put)('policies',data,policy._policy_id)
        broker.propagate(StateProtocol(service=AdminService))
        return {**data, **{'policy_id':policy._policy_id}}
        
    @UsePipe(FunctionInjectorPipe(fetch_policy,'policy'))
    @BaseHTTPRessource.HTTPRoute('/{policy}/',methods=[HTTPMethod.GET])
    async def read_policy(self,request:Request,policy:Annotated[PolicyModel,Depends(get_policy)],authPermission:AuthPermission=Depends(get_auth_permission)):
        return {**policy.model_dump(), **{'policy_id':policy._policy_id}}


@UsePermission(JWTRouteHTTPPermission)
@PingService([TortoiseConnectionService])
@LockService(TortoiseConnectionService,lockType='reader',infinite_wait=True,check_status=False)
@UseHandler(ServiceAvailabilityHandler,TortoiseHandler,AsyncIOHandler)
@HTTPRessource(CLIENT_PREFIX)
class ClientRessource(BaseHTTPRessource,IssueAuthInterface):

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
    @UseHandler(CostHandler,RedisHandler,VaultHandler,AuthClientHandler,SecurityHandler)
    @BaseHTTPRessource.Post('/')
    async def create_client(self,broker:Annotated[Broker,Depends(Broker)], merchant:Annotated[Merchant,Depends(Merchant)],cost:Annotated[DataCost,Depends(DataCost)],request:Request,response:Response, clientModel: ClientModel, authPermission:AuthPermission=Depends(get_auth_permission)):

        valid_policies = await RunInThreadPool(self.vaultService.security_engine.list)('policies')
        if len((policies_error:=set(clientModel).difference(valid_policies)))>0:
            raise PoliciesNotMatchingError(policies_error)

        client_data = { **clientModel.model_dump(),'can_login':False,'client_id':clientModel._client_id}
        await fetch_group(clientModel.group) if clientModel.group != None else None

        async def transaction():
            async with self.tortoiseService.transaction(SECURITY_CREDS) as ctx:
                mapping = [PolicyMappingORM(policy_id=policy_id,client=client,group=None) for policy_id in clientModel.policies]
                clientORM = await ClientORM.create(ctx,**client_data)
                await PolicyMappingORM.bulk_create(mapping,using_db=ctx)
                client = ClientMiniService(self.vaultService,self.configService,self.jwtAuthService,self.securityService,clientORM,[],id=...)
                await client.store_password(clientModel.password)
                await client.create_auth_signature()

        async def rollback():
            await RunInThreadPool(self.vaultService.secrets_engine.delete)('clients',clientModel._client_id)

        broker.propagate(StateProtocol(service=AdminService))

        return client_data

    @PingService([VaultService])
    @UsePermission(AdminPermission)
    @UsePipe(ObjectRelationalFriendlyPipe,before=False)
    @UsePipe(MiniServiceInjectorPipe(AdminService,'client'))
    @LockService(SettingService,VaultService,lockType='reader')
    @LockService(AdminService,as_manager=True,miniLockType='reader')
    @UseHandler(ValueErrorHandler,ORMCacheHandler,VaultHandler,SecurityHandler,MiniServiceHandler)
    @BaseHTTPRessource.HTTPRoute('/{client}/', methods=[HTTPMethod.PUT])
    async def update_client(self, updateClient:UpdateClientModel,broker:Annotated[Broker,Depends(Broker)],client: Annotated[ClientMiniService, Depends(get_client)],mode:PolicyUpdateMode = Depends(policy_update_mode_query),profile:str=Depends(get_client), authPermission:AuthPermission=Depends(get_auth_permission) ):

        group = await fetch_group(updateClient.group) if updateClient.group  else None
        async with self.tortoiseService.transaction(SECURITY_CREDS) as ctx:
            is_revoked = await client.update_client(updateClient,group,ctx)
            await self.adminService.update_policy(updateClient.policies,mode,client,group,ctx)
            if is_revoked: # ERROR Do i need the revoke the possibility to login again?
                await client.revoke_client(ctx)

            broker.propagate(StateProtocol(service=AdminService))
            return client.client

    @PingService([VaultService])        
    @UsePermission(AdminPermission)
    @HTTPStatusCode(status.HTTP_200_OK,)
    @UsePipe(ObjectRelationalFriendlyPipe,before=False)
    @UsePipe(MiniServiceInjectorPipe(AdminService,'client'))
    @LockService(SettingService,VaultService,lockType='reader')
    @LockService(AdminService,as_manager=True,miniLockType='reader')
    @UseInterceptor(DataCostInterceptor(CostConstant.CLIENT_CREDIT,'refund'))
    @UseHandler(ORMCacheHandler,CostHandler,RedisHandler,VaultHandler,SecurityHandler,MiniServiceHandler)
    @BaseHTTPRessource.Delete('/{client}/')
    async def delete_client(self,broker:Annotated[Broker,Depends(Broker)], merchant:Annotated[Merchant,Depends(Merchant)],cost:Annotated[DataCost,Depends(DataCost)],request:Request,response:Response, client: Annotated[ClientMiniService, Depends(get_client)],profile:str=Depends(get_client), authPermission:AuthPermission=Depends(get_auth_permission)):
        
        async def transaction():
            async with self.tortoiseService.transaction(SECURITY_CREDS,lock='reader') as ctx:
                client.delete_itself(ctx)
        
        merchant.safe_payment(
            None,
            None,
            transaction
        )
        broker.propagate(StateProtocol(service=AdminService))
        return client.client
    
    @UsePermission(AdminPermission)
    @LockService(AdminService,lockType='reader')
    @UseHandler(MiniServiceHandler,DataSourceHandler)
    @UsePipe(ObjectRelationalFriendlyPipe,before=False)
    @BaseHTTPRessource.Get('/{client:path}')
    async def read_client(self,request:Request,response:Response,client:str='',source:SourceMode=Depends(source_mode_query),authPermission:AuthPermission=Depends(get_auth_permission)):
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
                    return client
            case _:
                raise DataSourceNotSupportedError(source,['database','memory'])



    @PingService([VaultService])
    @UsePermission(AdminPermission)
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @LockService(VaultService,lockType='reader')
    @UseHandler(SecurityHandler,VaultHandler)
    @UsePipe(ObjectRelationalFriendlyPipe,before=False)
    @UseGuard(TortoiseHardLimitGuard(10,GroupClientORM))
    @BaseHTTPRessource.Post('/group/')
    async def create_group(self, groupModel: GroupModel,request:Request,response:Response, authPermission:AuthPermission=Depends(get_auth_permission)):

        valid_policies = await RunInThreadPool(self.vaultService.security_engine.list)('policies')
        if len((policies_error:=set(groupModel.policies).difference(valid_policies)))>0:
            raise PoliciesNotMatchingError(policies_error)

        async with self.tortoiseService.transaction(SECURITY_CREDS) as ctx:    
            group:GroupClientORM = await GroupClientORM.create(ctx,group_name=groupModel.group_name)
            await PolicyMappingORM.bulk_create([PolicyMappingORM(policy_id=policy_id,client=None,group=group) for policy_id in groupModel.policies],using_db=ctx)

        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Group successfully created", "group": group.to_json})

    @UseHandler(ORMCacheHandler)
    @UsePermission(AdminPermission)
    @LockService(AdminService,lockType='reader')
    @UsePipe(FunctionInjectorPipe(fetch_group,'group'))
    @UsePipe(ObjectRelationalFriendlyPipe,before=False)
    @BaseHTTPRessource.Delete('/group/{group}/')
    async def delete_group(self,broker:Annotated[Broker,Depends(Broker)],request:Request,response:Response, group: Annotated[GroupClientORM, Depends(get_group)], authPermission:AuthPermission=Depends(get_auth_permission)):

        async with self.tortoiseService.transaction(SECURITY_CREDS) as ctx:
            await group.delete()
            await BlacklistORMCache.InvalidAll([group.group_id,WILDCARD])

        broker.propagate(StateProtocol(service=AdminService))

        return JSONResponse(status_code=status.HTTP_200_OK, content={"group": group.to_json})

    @UsePermission(AdminPermission)
    @UsePipe(ObjectRelationalFriendlyPipe,before=False)
    @BaseHTTPRessource.Get('/group/{group:path}')
    async def read_group(self,request:Request,response:Response,group:str='',authPermission:AuthPermission=Depends(get_auth_permission)):
        if group == '':
            return await GroupClientORM.all()
        else:
            return await fetch_group(group)
        
@UseHandler(ServiceAvailabilityHandler)
@PingService([TortoiseConnectionService])
@UseHandler(TortoiseHandler,AsyncIOHandler)
@UsePermission(JWTRouteHTTPPermission,AdminPermission)
@LockService(TortoiseConnectionService,lockType='reader',infinite_wait=True,check_status=False)
@HTTPRessource(ADMIN_PREFIX, routers=[ClientRessource,PolicyRessource])
class AdminRessource(BaseHTTPRessource,IssueAuthInterface):

    class UnRevokeGenerationIDModel(BaseModel):
        version:int|None = None
        destroy:bool = False
        delete:bool = False
        version_to_delete:list[int] = []

    @InjectInMethod()
    def __init__(self, configService: ConfigService, jwtAuthService: JWTAuthService, securityService: SecurityService,tortoiseService:TortoiseConnectionService,vaultService:VaultService):
        BaseHTTPRessource.__init__(self)
        IssueAuthInterface.__init__(self,Get(AdminService))
        self.configService = configService
        self.jwtAuthService = jwtAuthService
        self.securityService = securityService
        self.tortoiseService = tortoiseService
        self.vaultService = vaultService

    @PingService([VaultService])
    @UseLimiter(limit_value='20/week')
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @LockService(VaultService,JWTAuthService,lockType='reader')
    @UseHandler(AuthClientHandler,ORMCacheHandler,RedisHandler,SecurityHandler)
    @BaseHTTPRessource.HTTPRoute('/blacklist/', methods=[HTTPMethod.POST])
    async def blacklist_tokens(self,blacklist:BlacklistModel, response:Response, request: Request,authPermission:AuthPermission=Depends(get_auth_permission)):
        if await BlacklistORMCache.Get() and not blacklist.force:
            raise IdentityAlreadyBlacklistedError()

        match blacklist.mode:
            case 'token':
                try:
                    clientInfo =  self.jwtAuthService.verify_client_token_permission(blacklist.identity)
                except:
                    raise SecurityIdentityNotResolvedError(blacklist.identity)
                if time.time() > clientInfo['expired_at']:
                    raise ...
                if clientInfo['client_id'] != blacklist.identity:
                    raise SecurityIdentityNotResolvedError(blacklist.identity,'Client Info does match the identity provided')
                client = await ClientORM.filter(client_id=blacklist.identity).first()
                if client == None:
                    raise ClientDoesNotExistError(blacklist.identity)
                path = f"{client.client_id}/auth-signature/"
                signature:AuthSignature = await RunInThreadPool(self.vaultService.security_engine.read)('clients',path)
                signature = await RunInThreadPool(self.vaultService.transit_engine.decrypt)(signature['signature'],'security-key')
                if signature != clientInfo['authz_id']:
                    raise AuthzSignatureMisMatchError(blacklist.identity)
            case 'client':
                client = await ClientORM.filter(client_id=blacklist.identity).first()
                if client == None:
                    raise ClientDoesNotExistError(blacklist.identity)
            case 'group':
                await fetch_group(blacklist.identity)                

        await BlacklistORMCache.Store(blacklist.identity,True,blacklist.time)

    @UseLimiter(limit_value='20/week')
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @UseHandler(AuthClientHandler,ORMCacheHandler,SecurityHandler,RedisHandler)
    @BaseHTTPRessource.HTTPRoute('/blacklist/', methods=[HTTPMethod.DELETE])
    async def un_blacklist_tokens(self, blacklist:BlacklistModel,response:Response, request: Request, authPermission:AuthPermission=Depends(get_auth_permission)):
        if not await BlacklistORMCache.Get(blacklist.identity):
            raise IdentityAlreadyBlacklistedError(blacklist.identity,blacklist.mode,reversed_=True)

        await BlacklistORMCache.Invalid(blacklist.identity)

    @PingService([VaultService])
    @UseLimiter(limit_value='1/day')
    @UseHandler(AuthClientHandler,ORMCacheHandler)
    @LockService(VaultService,SettingService,JWTAuthService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/revoke-all/', methods=[HTTPMethod.DELETE],deprecated=True,mount=False)
    async def revoke_all_tokens(self, request: Request, broker:Annotated[Broker,Depends(Broker)], authPermission:AuthPermission=Depends(get_auth_permission)):
        await self.adminService.revoke_all_tokens()

        broker.propagate(StateProtocol(
            service=self.jwtAuthService.name,
            to_build=True,
            bypass_async_verify=True,
            force_sync_verify=True
        ))

        client = await ClientORM.filter(client_id=authPermission['client_id']).first()
        auth_token, refresh_token = self.issue_auth(client)
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Tokens successfully invalidated",
                                                                     "details": "Even if you're the admin old token wont be valid anymore",
                                                                     "tokens": {"refresh_token": refresh_token, "auth_token": auth_token},
                                                                     })
    
    @PingService([VaultService])
    @UseLimiter(limit_value='1/day')
    @LockService(SettingService,lockType='reader')
    @LockService(VaultService,lockType='reader',check_status=False)
    @LockService(JWTAuthService,lockType='writer')
    @UseHandler(AuthClientHandler)
    @BaseHTTPRessource.HTTPRoute('/unrevoke-all/', methods=[HTTPMethod.POST],deprecated=True,mount=False)
    async def un_revoke_all_tokens(self, request: Request, unRevokeModel:UnRevokeGenerationIDModel, broker:Annotated[Broker,Depends(Broker)], authPermission:AuthPermission=Depends(get_auth_permission)):   
        unRevokeModel = unRevokeModel.model_dump()
        await self.adminService.unrevoke_all_tokens(**unRevokeModel)
        
        broker.propagate(StateProtocol(
            service=self.jwtAuthService.name,
            to_build=True,
            bypass_async_verify=True,
            force_sync_verify=True
        ))

        client = await ClientORM.filter(client_id=authPermission['client_id']).first()
        auth_token, refresh_token = await self.issue_auth(client)

        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Tokens successfully invalidated",
                                                                     "details": "Even if you're the admin old token wont be valid anymore",
                                                                     "tokens": {"refresh_token": refresh_token, "auth_token": auth_token},})

    @LockService(JWTAuthService,lockType='reader')
    @UseLimiter(limit_value='1/day')
    @BaseHTTPRessource.HTTPRoute('/revoke-version/', methods=[HTTPMethod.GET],deprecated=True,mount=False)
    def check_version(self,request:Request):
        return self.jwtAuthService.GENERATION_METADATA

    @UseLimiter(limit_value='10/day')
    @UsePipe(ForceClientPipe)
    @UseGuard(AuthenticatedClientGuard)
    @UseHandler(ORMCacheHandler)
    @BaseHTTPRessource.HTTPRoute('/revoke/', methods=[HTTPMethod.DELETE])
    async def revoke_tokens(self, request: Request, client: Annotated[ClientORM, Depends(get_client)], authPermission=Depends(get_auth_permission)):
        async with self.tortoiseService.transaction(SECURITY_CREDS):    
            await self._revoke_client(client)
            client.can_login = False #QUESTION Can be set to True?
            if client.can_login:
                await self.change_authz_id(challenge)
                
            await client.save()
        
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Tokens successfully revoked", "client": client.to_json})

    @UseLimiter(limit_value='4/day')
    @UsePipe(ForceClientPipe)
    @UseHandler(AuthClientHandler,ORMCacheHandler)
    @LockService(SettingService,lockType='reader')
    @UseGuard(BlacklistClientGuard, AuthenticatedClientGuard(reverse=True))
    @BaseHTTPRessource.HTTPRoute('/issue-auth/', methods=[HTTPMethod.GET])
    async def issue_auth_token(self, client: Annotated[ClientORM, Depends(get_client)], request: Request, authPermission=Depends(get_auth_permission)):
        
        async with self.tortoiseService.transaction(SECURITY_CREDS):    
            await raw_revoke_challenges(client)

            auth_token, refresh_token = await self.issue_auth(client,True)
            client.authenticated = True
            client.can_login = True
            await client.save()

        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": {
            "refresh_token": refresh_token, "auth_token": auth_token}, "message": "Tokens successfully issued"})

