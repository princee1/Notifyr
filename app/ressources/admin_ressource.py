from dataclasses import dataclass
from typing import Annotated, Any, List, Optional
from fastapi import Depends, Query, Request, HTTPException, status
from fastapi.responses import JSONResponse
from app.decorators.guards import AuthenticatedClientGuard, BlacklistClientGuard
from app.decorators.my_depends import get_blacklist, get_group, get_client
from app.interface.issue_auth import IssueAuthInterface
from app.models.security_model import BlacklistORM, ChallengeORM, ClientModel, ClientORM, GroupClientORM, GroupModel, UpdateClientModel, raw_revoke_challenges
from app.services.admin_service import AdminService
from app.services.celery_service import CeleryService
from app.services.security_service import JWTAuthService, SecurityService
from app.services.config_service import ConfigService
from app.utils.constant import ConfigAppConstant
from app.utils.dependencies import get_auth_permission, get_query_params, get_request_id
from app.container import InjectInMethod, Get
from app.definition._ressource import PingService, UseGuard, UseHandler, UsePermission, BaseHTTPRessource, HTTPMethod, HTTPRessource, UsePipe, UseRoles, UseLimiter
from app.decorators.permissions import AdminPermission, JWTRouteHTTPPermission
from app.classes.auth_permission import Role, RoutePermission, AssetsPermission, Scope, TokensModel
from pydantic import BaseModel,  field_validator
from app.decorators.handlers import SecurityClientHandler, ServiceAvailabilityHandler, TortoiseHandler, ValueErrorHandler
from app.decorators.pipes import  ForceClientPipe, ForceGroupPipe
from app.utils.helper import parseToBool
from app.utils.validation import ipv4_subnet_validator, ipv4_validator
from slowapi.util import get_remote_address
from app.errors.security_error import GroupIdNotMatchError, SecurityIdentityNotResolvedError
from datetime import datetime, timedelta

ADMIN_PREFIX = 'admin'
CLIENT_PREFIX = 'client'


class AuthPermissionModel(BaseModel):
    allowed_routes: dict[str, RoutePermission] = []
    allowed_assets: Optional[dict[str, AssetsPermission]] ={}
    roles: Optional[list[Role]] = [Role.PUBLIC]
    scope: Scope = None

    @field_validator('scope')
    def enforce_scope(cls,scope):
        return None
    
    @field_validator('roles')
    def checks_roles(cls, roles: list[Role]):
        if Role.PUBLIC not in roles:
            roles.append(Role.PUBLIC)
        return roles
        return [r.value for r in roles]

class GenerationModel(BaseModel):
    generation_id: str


@UseRoles([Role.ADMIN])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler,TortoiseHandler)
@HTTPRessource(CLIENT_PREFIX)
class ClientRessource(BaseHTTPRessource,IssueAuthInterface):

    @InjectInMethod
    def __init__(self, configService: ConfigService, securityService: SecurityService, jwtAuthService: JWTAuthService, adminService: AdminService):
        super().__init__()
        self.configService = configService
        self.securityService = securityService
        self.jwtAuthService = jwtAuthService
        self.adminService = adminService

        self.key = self.configService.getenv('CLIENT_PASSWORD_HASH_KEY','test')

    @UsePermission(AdminPermission)
    @BaseHTTPRessource.Post('/')
    async def create_client(self, client: ClientModel,gid: str = Depends(get_query_params('gid', 'id')), authPermission=Depends(get_auth_permission)):
        name = client.client_name
        scope = client.client_scope
        password,salt = self.securityService.store_password(client.password,self.key)
        salt = str(salt)
        
        group_id = client.group_id
        if group_id != None :
            group = await get_group(group_id=group_id,gid=gid,authPermission=authPermission)
        else:
            group = None

        client:ClientORM = await ClientORM.create(client_name=name, client_scope=scope, group=group,issued_for=client.issued_for,password=password,password_salt=salt,can_login=False)
        challenge = await ChallengeORM.create(client=client)
        challenge.expired_at_auth = challenge.created_at_auth + timedelta(seconds=self.configService.AUTH_EXPIRATION)
        challenge.expired_at_refresh = challenge.created_at_refresh + timedelta(seconds=self.configService.REFRESH_EXPIRATION)
        await challenge.save()

        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Client successfully created", "client": client.to_json})
    
    @UsePermission(AdminPermission)
    @UsePipe(ForceClientPipe)
    @UseHandler(ValueErrorHandler)
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.PUT])
    async def update_client(self, updateClient:UpdateClientModel ,client: Annotated[ClientORM, Depends(get_client)],gid: str = Depends(get_query_params('gid', 'id')),rmgrp: str = Depends(get_query_params('rmgrp', False)),authPermission=Depends(get_auth_permission) ):
        
        if not isinstance(rmgrp,bool):
            rmgrp_ = parseToBool(rmgrp)
            if rmgrp_ == None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=f'Could not parse {rmgrp} as a bool')

        is_revoked = await self._update_client(updateClient, client, gid, authPermission,rmgrp_)
        if is_revoked:
            # ERROR Do i need the revoke the possibility to login again?
            await self._revoke_client(client)
        else:
            await client.save()

        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Client successfully updated", "client": client.to_json})


    @UsePermission(AdminPermission)
    @UsePipe(ForceClientPipe)
    @BaseHTTPRessource.Delete('/')
    async def delete_client(self, client: Annotated[ClientORM, Depends(get_client)], authPermission=Depends(get_auth_permission)):
        await client.delete()
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
    async def create_group(self, group: GroupModel, authPermission=Depends(get_auth_permission)):
        group_name = group.group_name
        group:GroupClientORM = await GroupClientORM.create(group_name=group_name) # BUG supposed to return an erro
        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Group successfully created", "group": group.to_json})

    @UsePermission(AdminPermission)
    @UsePipe(ForceGroupPipe)
    @BaseHTTPRessource.Delete('/group/')
    async def delete_group(self, group: Annotated[GroupClientORM, Depends(get_group)], authPermission=Depends(get_auth_permission)):
        await group.delete()
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
            else:
                if not ipv4_subnet_validator(client.issued_for):
                    raise ValueError(f"Invalid IPv4 subnet: {client.issued_for}")
                
        return is_revoked

@UseHandler(TortoiseHandler)
@UseRoles([Role.ADMIN])
@UsePermission(JWTRouteHTTPPermission,AdminPermission)
@UseHandler(ServiceAvailabilityHandler)
@HTTPRessource(ADMIN_PREFIX, routers=[ClientRessource])
class AdminRessource(BaseHTTPRessource,IssueAuthInterface):

    @InjectInMethod
    def __init__(self, configService: ConfigService, jwtAuthService: JWTAuthService, securityService: SecurityService):
        BaseHTTPRessource.__init__(self)
        IssueAuthInterface.__init__(self,Get(AdminService))
        self.configService = configService
        self.jwtAuthService = jwtAuthService
        self.securityService = securityService
        self.celeryService: CeleryService = Get(CeleryService)

    @UseLimiter(limit_value='20/week')
    @UseHandler(SecurityClientHandler)
    @BaseHTTPRessource.HTTPRoute('/blacklist/', methods=[HTTPMethod.POST])
    async def blacklist_tokens(self, group: Annotated[GroupClientORM, Depends(get_group)], client: Annotated[ClientORM, Depends(get_client)], request: Request,time:float =Query(3600,le=36000,ge=3600), authPermission=Depends(get_auth_permission)):
        if group is None and client is None:
            raise SecurityIdentityNotResolvedError

        if group is not None and client is not None and client.group_id != group.group_id:
            raise GroupIdNotMatchError(str(client.group_id), group.group_id)

        blacklist = await self.adminService.blacklist(client, group,time)
        # if blacklist == None:
        #     return JSONResponse(status_code=status.HTTP_204_NO_CONTENT,content={"message":"Client already blacklisted"})
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Tokens successfully blacklisted", "blacklist": blacklist.to_json})

    @UseLimiter(limit_value='20/week')
    @UseHandler(SecurityClientHandler)
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
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Tokens successfully un-blacklisted", "un_blacklist": blacklist})

    @UseLimiter(limit_value='1/day')
    @UseHandler(SecurityClientHandler)
    @BaseHTTPRessource.HTTPRoute('/revoke-all/', methods=[HTTPMethod.DELETE],deprecated=True,mount=False)
    async def revoke_all_tokens(self, request: Request, authPermission=Depends(get_auth_permission)):
        old_generation_id = self.jwtAuthService.generation_id
        self.jwtAuthService.set_generation_id(True)
        new_generation_id = self.configService.config_json_app[ConfigAppConstant.META_KEY][ConfigAppConstant.GENERATION_ID_KEY]

        client = await ClientORM.filter(client_id=authPermission['client_id']).first()
        auth_token, refresh_token = self.issue_auth(client, authPermission)

        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Tokens successfully invalidated",
                                                                     "details": "Even if you're the admin old token wont be valid anymore",
                                                                     "tokens": {"refresh_token": refresh_token, "auth_token": auth_token},
                                                                     "old_generation_id": old_generation_id,
                                                                     "new_generation_id": new_generation_id})

    @UseLimiter(limit_value='1/day')
    @UseHandler(SecurityClientHandler)
    @BaseHTTPRessource.HTTPRoute('/unrevoke-all/', methods=[HTTPMethod.POST],deprecated=True,mount=False)
    async def un_revoke_all_tokens(self, request: Request, generation: GenerationModel, authPermission=Depends(get_auth_permission)):
        new_generation_id = generation.generation_id
        old_generation_id = self.configService.config_json_app[ConfigAppConstant.META_KEY][ConfigAppConstant.GENERATION_ID_KEY]
        self.configService.config_json_app[ConfigAppConstant.META_KEY][ConfigAppConstant.GENERATION_ID_KEY] = new_generation_id
        self.jwtAuthService.set_generation_id(False)

        client = await ClientORM.filter(client_id=authPermission['client_id']).first()
        auth_token, refresh_token = await self.issue_auth(client, authPermission)

        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Tokens successfully invalidated",
                                                                     "details": "Even if you're the admin old token wont be valid anymore",
                                                                     "old_generation_id": old_generation_id,
                                                                     "tokens": {"refresh_token": refresh_token, "auth_token": auth_token},
                                                                     "new_generation_id": new_generation_id})

    @UseLimiter(limit_value='10/day')
    @UsePipe(ForceClientPipe)
    @UseGuard(AuthenticatedClientGuard)
    @BaseHTTPRessource.HTTPRoute('/revoke/', methods=[HTTPMethod.DELETE])
    async def revoke_tokens(self, request: Request, client: Annotated[ClientORM, Depends(get_client)], authPermission=Depends(get_auth_permission)):
        await self._revoke_client(client)
        
        client.can_login = False #QUESTION Can be set to True?
        if client.can_login:
            challenge = await ChallengeORM.filter(client=client).first()
            await self.change_authz_id(challenge)
        
        await client.save()
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Tokens successfully revoked", "client": client.to_json})

    @UseLimiter(limit_value='4/day')
    @UsePipe(ForceClientPipe)
    @UseHandler(SecurityClientHandler)
    @UseGuard(BlacklistClientGuard, AuthenticatedClientGuard(reverse=True))
    @BaseHTTPRessource.HTTPRoute('/issue-auth/', methods=[HTTPMethod.GET])
    async def issue_auth_token(self, client: Annotated[ClientORM, Depends(get_client)], authModel: AuthPermissionModel, request: Request, authPermission=Depends(get_auth_permission)):
        await raw_revoke_challenges(client)
        authModel = authModel.model_dump()
        authModel['scope'] = client.client_scope

        auth_token, refresh_token = await self.issue_auth(client, authModel,True)
        client.authenticated = True
        client.can_login = True
        await client.save()

        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": {
            "refresh_token": refresh_token, "auth_token": auth_token}, "message": "Tokens successfully issued"})

