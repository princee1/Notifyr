from dataclasses import dataclass
from random import randint
from typing import Annotated, Any, List, Optional
from fastapi import Depends, Query, Request, HTTPException, Response, status
from fastapi.responses import JSONResponse
from app.decorators.guards import AuthenticatedClientGuard, BlacklistClientGuard, PolicyGuard
from app.decorators.interceptors import DataCostInterceptor
from app.definition._service import StateProtocol
from app.depends.class_dep import Broker
from app.depends.funcs_dep import GetPolicy, get_blacklist, get_group, get_client
from app.depends.orm_cache import WILDCARD, AuthPermissionCache, BlacklistORMCache, ChallengeORMCache, ClientORMCache, PolicyORMCache
from app.interface.issue_auth import IssueAuthInterface
from app.models.security_model import BlacklistORM, ChallengeORM, ClientModel, ClientORM, GroupClientORM, GroupModel, PolicyMappingORM, PolicyORM, UpdateClientModel, raw_revoke_challenges
from app.services.admin_service import AdminService
from app.services.database_service import TortoiseConnectionService
from app.services.profile_service import ProfileService
from app.services.secret_service import HCVaultService
from app.services.setting_service import SettingService
from app.services.task_service import CeleryService
from app.services.security_service import JWTAuthService, SecurityService
from app.services.config_service import ConfigService
from app.utils.constant import ConfigAppConstant, CostConstant
from app.depends.dependencies import get_auth_permission, get_query_params, get_request_id
from app.container import InjectInMethod, Get
from app.definition._ressource import PingService, UseInterceptor, UseServiceLock, UseGuard, UseHandler, UsePermission, BaseHTTPRessource, HTTPMethod, HTTPRessource, UsePipe, UseRoles, UseLimiter,HTTPStatusCode
from app.decorators.permissions import AdminPermission, JWTRouteHTTPPermission
from app.classes.auth_permission import AuthType, PolicyModel, PolicyUpdateMode, Role, Scope
from pydantic import BaseModel,  field_validator
from app.decorators.handlers import AsyncIOHandler, CostHandler, ORMCacheHandler, PydanticHandler, SecurityClientHandler, ServiceAvailabilityHandler, TortoiseHandler, ValueErrorHandler
from app.decorators.pipes import  ForceClientPipe, ForceGroupPipe, ObjectRelationalFriendlyPipe
from app.utils.helper import filter_paths, parseToBool
from app.utils.validation import ipv4_subnet_validator, ipv4_validator
from slowapi.util import get_remote_address
from app.errors.security_error import GroupIdNotMatchError, SecurityIdentityNotResolvedError
from datetime import datetime, timedelta
from tortoise.transactions import in_transaction
from app.depends.variables import policy_update_mode_query
from tortoise.expressions import Q

ADMIN_PREFIX = 'admin'
CLIENT_PREFIX = 'client'

class UnRevokeGenerationIDModel(BaseModel):
    version:int|None = None
    destroy:bool = False
    delete:bool = False
    version_to_delete:list[int] = []


get_policy = GetPolicy(False)

@PingService([TortoiseConnectionService],infinite_wait=True)
@UseServiceLock(TortoiseConnectionService,lockType='reader',infinite_wait=True,check_status=False)
@UsePermission(JWTRouteHTTPPermission,AdminPermission)
@UseRoles(roles=[Role.ADMIN])
@UseHandler(ServiceAvailabilityHandler,TortoiseHandler,AsyncIOHandler)
@HTTPRessource('policy')
class PolicyRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,adminService:AdminService):
        super().__init__()
        self.adminService = adminService

    @PingService([ProfileService])
    @UseServiceLock(ProfileService,lockType='reader',check_status=False)
    @UsePipe(ObjectRelationalFriendlyPipe,before=False)
    @UseGuard(PolicyGuard)
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
    async def create_policy(self,request:Request,response:Response, policyModel:PolicyModel, authPermission=Depends(get_auth_permission)):
        policy_model = policyModel.model_dump(mode='python')

        async with in_transaction():
            policy_orm =  await PolicyORM.create(**policy_model)
            policy_id = str(policy_orm.policy_id)

            await PolicyORMCache.Store(policy_id,policy_orm)
            return policy_orm
    
    @UsePipe(ObjectRelationalFriendlyPipe,before=False)
    @BaseHTTPRessource.HTTPRoute('/{policy}/',methods=[HTTPMethod.DELETE])
    async def delete_policy(self,request:Request,policy:Annotated[PolicyORM,Depends(get_policy)],authPermission=Depends(get_auth_permission)):
        async with in_transaction():
            await policy.delete()
            await PolicyORMCache.Invalid(str(policy.policy_id))
            await AuthPermissionCache.InvalidAll()
        
        return policy

    @PingService([ProfileService])
    @UseServiceLock(ProfileService,lockType='reader',check_status=False)
    @UseHandler(PydanticHandler)
    @UseGuard(PolicyGuard)
    @UsePipe(ObjectRelationalFriendlyPipe,before=False)
    @BaseHTTPRessource.HTTPRoute('/{policy}/',methods=[HTTPMethod.PUT])
    async def update_policy(self,request:Request,policyModel:PolicyModel,policy:Annotated[PolicyORM,Depends(get_policy)],mode:PolicyUpdateMode =Depends(policy_update_mode_query), authPermission=Depends(get_auth_permission)):
        
        async with in_transaction():
            self._update_policy_model(policyModel,mode,policy)
            await policy.save()
            policy_id = str(policy.policy_id)
            await PolicyORMCache.Invalid(policy_id)
            await PolicyORMCache.Store(policy_id,policy)
            await AuthPermissionCache.InvalidAll()

        return policy
    
    @UsePipe(ObjectRelationalFriendlyPipe,before=False)
    @BaseHTTPRessource.HTTPRoute('/{policy}/',methods=[HTTPMethod.GET])
    async def read_policy(self,request:Request,policy:Annotated[PolicyORM,Depends(get_policy)],authPermission=Depends(get_auth_permission)):
        return policy

    def _update_policy_model(self,model:PolicyModel,mode:PolicyUpdateMode,policy:PolicyORM):
        match mode:

            case 'merge':    
                policy.allowed_assets = list(set(model.allowed_assets + policy.allowed_assets))
                policy.allowed_profiles = list(set(model.allowed_profiles +policy.allowed_profiles))
                policy.allowed_agents = list(set(model.allowed_agents +policy.allowed_agents))
                policy.roles = list(set(model.roles + policy.roles))
                policy.allowed_routes = {**policy.allowed_routes,**model.allowed_routes}
            
            case 'set':
                policy.allowed_assets = model.allowed_assets
                policy.allowed_profiles = model.allowed_profiles
                policy.roles = model.roles
                policy.allowed_routes = model.allowed_routes
                policy.allowed_agents = model.allowed_agents
            
            case 'delete':
                policy.allowed_assets = list(set(policy.allowed_assets) - set(model.allowed_assets))
                policy.allowed_profiles = list(set(policy.allowed_profiles) - set(model.allowed_profiles))
                policy.roles = list(set(policy.roles) - set(model.roles))
                policy.allowed_agents = list(set(policy.allowed_agents) - set(model.allowed_agents))
                policy.allowed_routes = {k: v for k, v in policy.allowed_routes.items() if k not in model.allowed_routes}

        
@PingService([TortoiseConnectionService])
@UseServiceLock(TortoiseConnectionService,lockType='reader',infinite_wait=True,check_status=False)
@UseRoles([Role.ADMIN])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler,TortoiseHandler,AsyncIOHandler)
@HTTPRessource(CLIENT_PREFIX)
class ClientRessource(BaseHTTPRessource,IssueAuthInterface):

    @InjectInMethod()
    def __init__(self, configService: ConfigService, securityService: SecurityService, jwtAuthService: JWTAuthService, adminService: AdminService):
        super().__init__()
        self.configService = configService
        self.securityService = securityService
        self.jwtAuthService = jwtAuthService
        self.adminService = adminService

        self.settingService = Get(SettingService)
        self.vaultService = Get(HCVaultService)

        self.key = self.vaultService.CLIENT_PASSWORD_HASH_KEY

    @UseHandler(CostHandler)
    @UseInterceptor(DataCostInterceptor(CostConstant.CLIENT_CREDIT))
    @UseServiceLock(SettingService,lockType='reader')
    @UsePermission(AdminPermission)
    @BaseHTTPRessource.Post('/')
    async def create_client(self, client: ClientModel,gid: str = Depends(get_query_params('gid', 'id')), authPermission=Depends(get_auth_permission)):
        
        policy_ids = client.policy_ids
        password, salt = self.securityService.store_password(client.password, self.key)
        client_data = {
            "client_name": client.client_name,"client_scope": client.client_scope,"group": None,"password": password,"password_salt": str(salt),"can_login": False,
            "client_description": client.client_description,
            "auth_type": client.auth_type,
        }
        if client.client_scope in [Scope.SoloDolo, Scope.Organization]:
            client_data['issued_for'] = client.issued_for

        group_id = client.group_id
        if group_id != None :
            group = await get_group(group_id=group_id,gid=gid,authPermission=authPermission)
        else:
            group = None

        async with in_transaction():
            group_id = None if group == None else str(group.group_id)
            client_data['group'] = group

            client:ClientORM = await ClientORM.create(**client_data)
            await PolicyMappingORM.bulk_create([PolicyMappingORM(policy_id=policy_id,client=client,group=None) for policy_id in policy_ids])
            challenge, ttl_auth_challenge = await self.create_challenge(client)

            await ClientORMCache.Store([group_id,client.client_id],client,)
            await ChallengeORMCache.Store(client.client_id,challenge,ttl_auth_challenge)

            policy = await AuthPermissionCache.Cache([group_id,client.client_id],client=client)

        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Client successfully created", "client": client.to_json,
                                                                          "Policy":policy})

    async def create_challenge(self, client: ClientORM):
        challenge = ChallengeORM(client=client)
        if client.auth_type == AuthType.API_TOKEN:
            challenge.expired_at_auth = None
            challenge.expired_at_refresh = None
            await challenge.save()
            return challenge, 0
        else:
            ttl_auth_challenge = timedelta(seconds=self.settingService.AUTH_EXPIRATION * 4)
            challenge.expired_at_auth = challenge.created_at_auth + ttl_auth_challenge
            challenge.expired_at_refresh = challenge.created_at_refresh + timedelta(seconds=self.settingService.REFRESH_EXPIRATION * 4)
            await challenge.save()
        return challenge, ttl_auth_challenge
    
    @UsePermission(AdminPermission)
    @UsePipe(ForceClientPipe)
    @UseHandler(ValueErrorHandler,ORMCacheHandler)
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.PUT])
    async def update_client(self, updateClient:UpdateClientModel ,client: Annotated[ClientORM, Depends(get_client)],gid: str = Depends(get_query_params('gid', 'id')),rmgrp: str = Depends(get_query_params('rmgrp', False)),mode:PolicyUpdateMode =Depends(policy_update_mode_query),authPermission=Depends(get_auth_permission) ):
        
        if not isinstance(rmgrp,bool):
            rmgrp_ = parseToBool(rmgrp)
            if rmgrp_ == None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=f'Could not parse {rmgrp} as a bool')
        async with in_transaction():
            is_revoked = await self._update_client(updateClient, client, gid, authPermission,rmgrp_)
            await self._update_policy(updateClient.policy_ids,mode,client)
            if is_revoked:
                # ERROR Do i need the revoke the possibility to login again?
                await self._revoke_client(client)
            else:
                await client.save()
            group_id = None if client.group == None else str(client.group.group_id)
            
            await ClientORMCache.Invalid([group_id,client.client_id])
            await ClientORMCache.Store([group_id,client.client_id],client)

            await AuthPermissionCache.Invalid([group_id,client.client_id])
            policy = await AuthPermissionCache.Cache([group_id,client.client_id],client=client)


        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Client successfully updated", "client": client.to_json,'Policy':policy})

    @UsePermission(AdminPermission)
    @UsePipe(ForceClientPipe)
    @UseHandler(ORMCacheHandler,CostHandler)
    @UseInterceptor(DataCostInterceptor(CostConstant.CLIENT_CREDIT,'refund'))
    @BaseHTTPRessource.Delete('/')
    async def delete_client(self, client: Annotated[ClientORM, Depends(get_client)], authPermission=Depends(get_auth_permission)):
        async with in_transaction():
            await client.delete()

            group_id = None if client.group==None else str(client.group.group_id)

            await ClientORMCache.Invalid([group_id,client.client_id])
            await AuthPermissionCache.Invalid([group_id,client.client_id])

        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Client successfully deleted", "client": client.to_json})

    @UseRoles(roles=[Role.CONTACTS])
    @BaseHTTPRessource.Get('/all',deprecated=True,mount=False)
    async def get_all_client(self, authPermission=Depends(get_auth_permission)):
        ...
    
    @UsePipe(ForceClientPipe)
    @UseRoles(roles=[Role.CONTACTS])
    @BaseHTTPRessource.Get('/', deprecated=True)
    async def get_client(self, client: Annotated[ClientORM, Depends(get_client)], authPermission=Depends(get_auth_permission)):
        return JSONResponse(status_code=status.HTTP_200_OK, content={"client": client.to_json})
        
    @UsePermission(AdminPermission)
    @BaseHTTPRessource.Post('/group/')
    async def create_group(self, groupModel: GroupModel, authPermission=Depends(get_auth_permission)):
        
        async with in_transaction():    
            group:GroupClientORM = await GroupClientORM.create(group_name=groupModel.group_name)
            await PolicyMappingORM.bulk_create([PolicyMappingORM(policy_id=policy_id,client=None,group=group) for policy_id in groupModel.policy_ids])

        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Group successfully created", "group": group.to_json})

    @UsePermission(AdminPermission)
    @UsePipe(ForceGroupPipe)
    @UseHandler(ORMCacheHandler)
    @BaseHTTPRessource.Delete('/group/')
    async def delete_group(self, group: Annotated[GroupClientORM, Depends(get_group)], authPermission=Depends(get_auth_permission)):
        async with in_transaction():

            await group.delete()
            await BlacklistORMCache.InvalidAll([group.group_id,WILDCARD])
            await AuthPermissionCache.InvalidAll([group.group_id,WILDCARD])
            
            return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Group successfully deleted", "group": group.to_json})

    @UseRoles(roles=[Role.CONTACTS])
    @BaseHTTPRessource.Get('/group/all/',deprecated=True,mount=False)
    async def get_all_group(self, authPermission=Depends(get_auth_permission)):
        ...

    @UseRoles(roles=[Role.CONTACTS])
    @UsePipe(ForceGroupPipe)
    @BaseHTTPRessource.Get('/group/', deprecated=True)
    async def get_single_group(self, group: Annotated[GroupClientORM, Depends(get_group)], authPermission=Depends(get_auth_permission)):
        return JSONResponse(status_code=status.HTTP_200_OK, content={"group": group.to_json})
    
    async def _update_client(self, updateClient:UpdateClientModel, client:ClientORM, gid:str, authPermission,rm_group:bool):
        is_revoked=False

        if updateClient.group_id:
            group = await get_group(group_id=updateClient.group_id,gid=gid,authPermission=authPermission)
            client.group=group
            is_revoked = True
        else :
            if rm_group:
                client.group = None
                is_revoked = True

        if updateClient.password:
            password,salt = self.securityService.store_password(client.password,self.key)
            salt = str(salt)
            client.password = password
            client.password_salt= salt
            is_revoked = True
        
        if updateClient.client_description != None:
            client.client_description = updateClient.client_description

        if updateClient.client_name:
            client.client_name = updateClient.client_name
        
        if updateClient.client_scope and client.client_scope != updateClient.client_scope:
            client.client_scope = updateClient.client_scope
            is_revoked = True
        
        if updateClient.issued_for and client.issued_for != updateClient.issued_for:
            client.issued_for = updateClient.issued_for
            is_revoked = True

        else:
            if client.client_scope == Scope.SoloDolo:
                if not ipv4_validator(client.issued_for):
                    raise ValueError(f"Invalid IPv4 address: {client.issued_for}")
            elif client.client_scope == Scope.Organization:
                if not ipv4_subnet_validator(client.issued_for):
                    raise ValueError(f"Invalid IPv4 subnet: {client.issued_for}")
                
        return is_revoked

    async def _update_policy(self, policy_ids: list[str], mode: PolicyUpdateMode, client: ClientORM = None, group: GroupClientORM = None):
        # Get all current policy mappings for this client/group
        current_policies = PolicyMappingORM.filter(client=client, group=group)
        
        match mode:
            case 'delete':
                await current_policies.filter(Q(policy_id__in=policy_ids)).delete()

            case 'merge':
                # Add new policy_ids that are not already mapped
                current_policies = await current_policies
                current_policy_ids = {pm.policy_id for pm in current_policies}
                new_policy_ids = set(policy_ids) - current_policy_ids
                await PolicyMappingORM.bulk_create([
                    PolicyMappingORM(policy_id=pid, client=client, group=group)
                    for pid in new_policy_ids
                ])

            case 'set':
                # Remove all current mappings, then set only the provided policy_ids
                await current_policies.delete()
                await PolicyMappingORM.bulk_create([
                    PolicyMappingORM(policy_id=pid, client=client, group=group)
                    for pid in policy_ids
                ])

@PingService([TortoiseConnectionService])
@UseServiceLock(TortoiseConnectionService,lockType='reader',infinite_wait=True,check_status=False)
@UseHandler(TortoiseHandler,AsyncIOHandler)
@UseRoles([Role.ADMIN])
@UsePermission(JWTRouteHTTPPermission,AdminPermission)
@UseHandler(ServiceAvailabilityHandler)
@HTTPRessource(ADMIN_PREFIX, routers=[ClientRessource,PolicyRessource])
class AdminRessource(BaseHTTPRessource,IssueAuthInterface):

    @InjectInMethod()
    def __init__(self, configService: ConfigService, jwtAuthService: JWTAuthService, securityService: SecurityService):
        BaseHTTPRessource.__init__(self)
        IssueAuthInterface.__init__(self,Get(AdminService))
        self.configService = configService
        self.jwtAuthService = jwtAuthService
        self.securityService = securityService
        self.celeryService: CeleryService = Get(CeleryService)

    @UseLimiter(limit_value='20/week')
    @UseHandler(SecurityClientHandler,ORMCacheHandler)
    @BaseHTTPRessource.HTTPRoute('/blacklist/', methods=[HTTPMethod.POST])
    async def blacklist_tokens(self, group: Annotated[GroupClientORM, Depends(get_group)], client: Annotated[ClientORM, Depends(get_client)], request: Request,time:float =Query(3600,le=36000,ge=3600), authPermission=Depends(get_auth_permission)):
        if group is None and client is None:
            raise SecurityIdentityNotResolvedError

        if group is not None and client is not None and client.group_id != group.group_id:
            raise GroupIdNotMatchError(str(client.group_id), group.group_id)

        blacklist = await self.adminService.blacklist(client, group,time)
        if blacklist.client != None:
            await BlacklistORMCache.Store(blacklist.client.client_id,True,time+randint(15,60))
        
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Tokens successfully blacklisted", "blacklist": blacklist.to_json})

    @UseLimiter(limit_value='20/week')
    @UseHandler(SecurityClientHandler,ORMCacheHandler)
    @BaseHTTPRessource.HTTPRoute('/blacklist/', methods=[HTTPMethod.DELETE])
    async def un_blacklist_tokens(self, group: Annotated[GroupClientORM, Depends(get_group)], client: Annotated[ClientORM, Depends(get_client)], blacklist:Annotated[BlacklistORM,Depends(get_blacklist)], request: Request, authPermission=Depends(get_auth_permission)):
        if blacklist is not None:
            await blacklist.delete()
            return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Blacklist entry successfully removed"})

        if group is None and client is None:
            raise SecurityIdentityNotResolvedError

        if group is not None and client is not None and client.group_id != group.group_id:
            raise GroupIdNotMatchError(str(client.group_id), str(group.group_id))

        blacklist = await self.adminService.un_blacklist(client, group)

        if blacklist.client != None:
            await BlacklistORMCache.Invalid(blacklist.client.client_id)
        else:
            await BlacklistORMCache.InvalidAll([blacklist.group.group_id,WILDCARD])

        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Tokens successfully un-blacklisted", "un_blacklist": blacklist})

    @PingService([HCVaultService])
    @UseLimiter(limit_value='1/day')
    @UseHandler(SecurityClientHandler,ORMCacheHandler)
    @UseServiceLock(SettingService,lockType='reader')
    @UseServiceLock(HCVaultService,lockType='reader',check_status=False)
    @UseServiceLock(JWTAuthService,lockType='writer')
    @BaseHTTPRessource.HTTPRoute('/revoke-all/', methods=[HTTPMethod.DELETE],deprecated=True,mount=False)
    async def revoke_all_tokens(self, request: Request, broker:Annotated[Broker,Depends(Broker)], authPermission=Depends(get_auth_permission)):
        self.jwtAuthService.revoke_all_tokens()

        broker.propagate_state(StateProtocol(
            service=self.jwtAuthService.name,
            to_build=True,
            bypass_async_verify=True,
            force_sync_verify=True
        ))

        client = await ClientORM.filter(client_id=authPermission['client_id']).first()
        auth_token, refresh_token = self.issue_auth(client)
        await ChallengeORMCache.InvalidAll()
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Tokens successfully invalidated",
                                                                     "details": "Even if you're the admin old token wont be valid anymore",
                                                                     "tokens": {"refresh_token": refresh_token, "auth_token": auth_token},
                                                                     })
    
    @PingService([HCVaultService])
    @UseLimiter(limit_value='1/day')
    @UseServiceLock(SettingService,lockType='reader')
    @UseServiceLock(HCVaultService,lockType='reader',check_status=False)
    @UseServiceLock(JWTAuthService,lockType='writer')
    @UseHandler(SecurityClientHandler)
    @BaseHTTPRessource.HTTPRoute('/unrevoke-all/', methods=[HTTPMethod.POST],deprecated=True,mount=False)
    async def un_revoke_all_tokens(self, request: Request, unRevokeModel:UnRevokeGenerationIDModel, broker:Annotated[Broker,Depends(Broker)], authPermission=Depends(get_auth_permission)):   
        unRevokeModel = unRevokeModel.model_dump()
        self.jwtAuthService.unrevoke_all_tokens(**unRevokeModel)
        
        broker.propagate_state(StateProtocol(
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

    @UseServiceLock(JWTAuthService,lockType='reader')
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
        async with in_transaction():    
            await self._revoke_client(client)
            client.can_login = False #QUESTION Can be set to True?
            if client.can_login:
                challenge = await ChallengeORM.filter(client=client).first()
                await self.change_authz_id(challenge)
                
            await client.save()
        
        await ClientORMCache.Invalid([client.group.group_id,client.client_id])
        await ChallengeORMCache.Invalid(client.client_id)

        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Tokens successfully revoked", "client": client.to_json})

    @UseLimiter(limit_value='4/day')
    @UsePipe(ForceClientPipe)
    @UseHandler(SecurityClientHandler,ORMCacheHandler)
    @UseServiceLock(SettingService,lockType='reader')
    @UseGuard(BlacklistClientGuard, AuthenticatedClientGuard(reverse=True))
    @BaseHTTPRessource.HTTPRoute('/issue-auth/', methods=[HTTPMethod.GET])
    async def issue_auth_token(self, client: Annotated[ClientORM, Depends(get_client)], request: Request, authPermission=Depends(get_auth_permission)):
        
        async with in_transaction():    
            await raw_revoke_challenges(client)

            auth_token, refresh_token = await self.issue_auth(client,True)
            client.authenticated = True
            client.can_login = True
            await client.save()

        await ChallengeORMCache.Invalid(client.client_id)

        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": {
            "refresh_token": refresh_token, "auth_token": auth_token}, "message": "Tokens successfully issued"})

