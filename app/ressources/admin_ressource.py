from dataclasses import dataclass
from typing import Annotated, Any, List, Optional
from fastapi import Depends, Header, Query, Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from app.decorators.guards import AuthenticatedClientGuard, BlacklistClientGuard, RefreshTokenGuard
from app.decorators.my_depends import get_client, get_group
from app.models.security_model import ChallengeORM, ClientModel, ClientORM, GroupClientORM, GroupModel, raw_revoke_challenge
from app.services.admin_service import AdminService
from app.services.celery_service import CeleryService
from app.services.security_service import JWTAuthService, SecurityService
from app.services.config_service import ConfigService
from app.utils.constant import ConfigAppConstant
from app.utils.dependencies import get_auth_permission, get_request_id
from app.container import InjectInMethod, Get
from app.definition._ressource import PingService, UseGuard, UseHandler, UsePermission, BaseHTTPRessource, HTTPMethod, HTTPRessource, UsePipe, UseRoles, UseLimiter
from app.decorators.permissions import AdminPermission, JWTRouteHTTPPermission
from app.classes.auth_permission import AuthPermission, Role, RoutePermission, AssetsPermission, Scope, TokensModel
from pydantic import BaseModel, RootModel, field_validator
from app.decorators.handlers import SecurityClientHandler, ServiceAvailabilityHandler, TortoiseHandler
from app.decorators.pipes import AuthPermissionPipe, ForceClientPipe, ForceGroupPipe, RefreshTokenPipe
from app.utils.validation import ipv4_validator
from slowapi.util import get_remote_address
from app.errors.security_error import GroupIdNotMatchError, SecurityIdentityNotResolvedError

ADMIN_PREFIX = 'admin'
CLIENT_PREFIX = 'client'


async def verify_admin_token(x_admin_token: Annotated[str, Header()]):
    configService: ConfigService = Get(ConfigService)

    if x_admin_token == None or x_admin_token != configService.ADMIN_KEY:
        raise HTTPException(
            status_code=403, detail="X-Admin-Token header invalid")


class AuthPermissionModel(BaseModel):
    allowed_routes: dict[str, RoutePermission]
    allowed_assets: Optional[dict[str, AssetsPermission]]
    roles: Optional[list[Role]] = [Role.PUBLIC]
    scope: Scope = Scope.SoloDolo

    @field_validator('issued_for')
    def check_issued_for(cls, issued_for: str):
        if not ipv4_validator(issued_for):
            raise ValueError('Invalid IP Address')
        return issued_for

    @field_validator('roles')
    def checks_roles(cls, roles: list[Role]):
        if Role.PUBLIC not in roles:
            roles.append(Role.PUBLIC)
        return roles


class GenerationModel(BaseModel):
    generation_id: str


@UseHandler(TortoiseHandler)
@UsePermission(AdminPermission)
@UseRoles([Role.ADMIN])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler)
@HTTPRessource(CLIENT_PREFIX)
class ClientRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self, configService: ConfigService, securityService: SecurityService, jwtAuthService: JWTAuthService, adminService: AdminService):
        super().__init__(dependencies=[Depends(verify_admin_token)])
        self.configService = configService
        self.securityService = securityService
        self.jwtAuthService = jwtAuthService
        self.adminService = adminService

    @BaseHTTPRessource.Post('/')
    async def create_client(self, client: ClientModel, authPermission=Depends(get_auth_permission)):
        name = client.client_name
        scope = client.scope

        group_id = client.group_id
        if group_id != None and not await GroupClientORM.exists(group=group_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Group not found")

        client = await ClientORM.create(client_name=name, client_scope=scope, group=group_id)
        await ChallengeORM.create(client=client)
        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Client successfully created", "client": client})

    @UsePipe(ForceGroupPipe)
    @UsePipe(ForceClientPipe)
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.PUT])
    async def add_client_to_group(self, client: Annotated[ClientORM, Depends(get_client)], group: Annotated[GroupClientORM, Depends(get_group)]):
        client.group_id = group
        await client.save()
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Client successfully added to group", "client": client})

    @UsePipe(ForceClientPipe)
    @BaseHTTPRessource.Delete('/')
    async def delete_client(self, client: Annotated[ClientORM, Depends(get_client)], authPermission=Depends(get_auth_permission)):
        await client.delete()
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Client successfully deleted", "client": client})

    @BaseHTTPRessource.Get('/')
    async def get_all_client(self, authPermission=Depends(get_auth_permission)):
        ...

    @BaseHTTPRessource.Post('/group/')
    async def create_group(self, group: GroupModel, authPermission=Depends(get_auth_permission)):
        group_name = group.group_name
        group = await GroupClientORM.create(group_name=group_name)
        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Group successfully created", "group": group})

    @UsePipe(ForceGroupPipe)
    @BaseHTTPRessource.Delete('/group/')
    async def delete_group(self, group: Annotated[GroupClientORM, Depends(get_group)], authPermission=Depends(get_auth_permission)):
        await group.delete()
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Group successfully deleted", "group": group})

    @BaseHTTPRessource.Get('/group/')
    async def get_all_group(self, authPermission=Depends(get_auth_permission)):
        ...


@UseHandler(TortoiseHandler)
@UseRoles([Role.ADMIN])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler)
@HTTPRessource(ADMIN_PREFIX, routers=[ClientRessource])
class AdminRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self, configService: ConfigService, jwtAuthService: JWTAuthService, securityService: SecurityService, adminService: AdminService):
        super().__init__(dependencies=[Depends(verify_admin_token)])
        self.configService = configService
        self.jwtAuthService = jwtAuthService
        self.securityService = securityService
        self.adminService = adminService
        self.celeryService: CeleryService = Get(CeleryService)

    @UseLimiter(limit_value='20/week')
    @UseHandler(SecurityClientHandler)
    @UsePermission(AdminPermission)
    @BaseHTTPRessource.HTTPRoute('/blacklist/{client_id}', methods=[HTTPMethod.POST])
    async def blacklist_tokens(self, group: Annotated[GroupClientORM, get_group], client: Annotated[ClientORM, Depends(get_client)], request: Request, authPermission=Depends(get_auth_permission)):
        if group == None and client == None:
            raise SecurityIdentityNotResolvedError
            

        if group != None and client != None and client.group_id != group.group_id:
            raise GroupIdNotMatchError(client.group_id, group.group_id)

        return await self.adminService.blacklist(client, group)

    @UseLimiter(limit_value='20/week')
    @UsePermission(AdminPermission)
    @UseHandler(SecurityClientHandler)
    @BaseHTTPRessource.HTTPRoute('/blacklist/{client_id}',methods=[HTTPMethod.DELETE])
    async def un_blacklist_tokens(self,group: Annotated[GroupClientORM, get_group], client: Annotated[ClientORM, Depends(get_client)], request: Request, authPermission=Depends(get_auth_permission)):
        if group == None and client == None:
            raise SecurityIdentityNotResolvedError

        if group != None and client != None and client.group_id != group.group_id:
            raise GroupIdNotMatchError(client.group_id, group.group_id)
            
        return await self.adminService.un_blacklist(client, group)

        


    @UseLimiter(limit_value='1/day')
    @UsePermission(AdminPermission)
    @UseHandler(SecurityClientHandler)
    @PingService([JWTAuthService])
    @BaseHTTPRessource.HTTPRoute('/revoke-all/', methods=[HTTPMethod.DELETE])
    async def revoke_all_tokens(self, request: Request, authPermission=Depends(get_auth_permission)):
        old_generation_id = self.configService.config_json_app[ConfigAppConstant.GENERATION_ID_KEY]
        self.jwtAuthService.set_generation_id(True)

        new_generation_id = self.configService.config_json_app[ConfigAppConstant.GENERATION_ID_KEY]
        self.configService.config_json_app.save()

        client = await ClientORM.filter(client=authPermission['client_id']).first()
        auth_token, refresh_token = self.adminService.issue_auth(client, authPermission)

        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Tokens successfully invalidated",
                                                                     "details": "Even if you're the admin old token wont be valid anymore",
                                                                     "tokens": {"refresh_token": refresh_token, "auth_token": auth_token},
                                                                     "old_generation_id": old_generation_id,
                                                                     "new_generation_id": new_generation_id})

    @UseLimiter(limit_value='1/day')
    @UsePermission(AdminPermission)
    @UseHandler(SecurityClientHandler)
    @PingService([JWTAuthService])
    @BaseHTTPRessource.HTTPRoute('/unrevoke-all/', methods=[HTTPMethod.POST])
    async def un_revoke_all_tokens(self, request: Request, generation: GenerationModel, authPermission=Depends(get_auth_permission)):
        old_generation_id = self.configService.config_json_app[ConfigAppConstant.GENERATION_ID_KEY]
        self.jwtAuthService.set_generation_id(True)
        new_generation_id = generation.generation_id

        self.configService.config_json_app[ConfigAppConstant.GENERATION_ID_KEY] = new_generation_id
        self.configService.config_json_app.save()

        client = await ClientORM.filter(client=authPermission['client_id']).first()
        auth_token, refresh_token = self.adminService.issue_auth(client, authPermission)

        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Tokens successfully invalidated",
                                                                     "details": "Even if you're the admin old token wont be valid anymore",
                                                                     "old_generation_id": old_generation_id,
                                                                     "tokens": {"refresh_token": refresh_token, "auth_token": auth_token},
                                                                     "new_generation_id": new_generation_id})

    @UseLimiter(limit_value='10/day')
    @UsePipe(ForceClientPipe)
    @UsePermission(AdminPermission)
    @UseGuard(AuthenticatedClientGuard)
    @PingService([JWTAuthService])
    @BaseHTTPRessource.HTTPRoute('/revoke/{client_id}', methods=[HTTPMethod.DELETE])
    async def revoke_tokens(self, request: Request, client: Annotated[ClientORM, Depends(get_client)], authPermission=Depends(get_auth_permission)):
        await raw_revoke_challenge(client)
        client.authenticated = False
        await client.save()

    @UseLimiter(limit_value='4/day')
    @UsePermission(AdminPermission)
    @UsePipe(ForceClientPipe)
    @UseHandler(SecurityClientHandler)
    @UseGuard(BlacklistClientGuard, AuthenticatedClientGuard(reverse=True))
    @PingService([JWTAuthService])
    @BaseHTTPRessource.HTTPRoute('/issue-auth/{client_id}', methods=[HTTPMethod.GET])
    async def issue_auth_token(self, client: Annotated[ClientORM, Depends(get_client)], authModel: AuthPermissionModel, request: Request, authPermission=Depends(get_auth_permission)):
        await raw_revoke_challenge(client)  # NOTE reset counter
        challenge = await ChallengeORM.filter(client=client).first()
        auth_token, refresh_token = await self.adminService.issue_auth(challenge, client, authModel)
        client.authenticated = True
        await client.save()
        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": {
            "refresh_token": refresh_token, "auth_token": auth_token}, "message": "Tokens successfully issued"})

    # VERIFY Once a month
    @UseLimiter(limit_value='1/day')
    # TODO add status permission check
    @UsePipe(AuthPermissionPipe)
    @UseGuard(BlacklistClientGuard, AuthenticatedClientGuard, RefreshTokenGuard)
    @PingService([JWTAuthService])
    @UseHandler(SecurityClientHandler)
    @UsePipe(ForceClientPipe, RefreshTokenPipe)
    @UseRoles(include=[Role.REFRESH])
    @BaseHTTPRessource.HTTPRoute('/refresh-auth/{client_id}', methods=[HTTPMethod.GET, HTTPMethod.POST], deprecated=True)
    async def refresh_auth_token(self, tokens: TokensModel, client: Annotated[ClientORM, Depends(get_client)], request: Request, authPermission=Depends(get_auth_permission)):
        await raw_revoke_challenge(client)
        auth_token, refresh_token = await self.issue_auth(client, authPermission)
        client.authenticated = True
        await client.save()
        return JSONResponse(status_code=status.HTTP_200_OK, content={"tokens": {
            "refresh_token": refresh_token, "auth_token": auth_token}, "message": "Tokens successfully refreshed"})

    async def issue_auth(self, client, authPermission):
        challenge = await ChallengeORM.filter(client=client).first()
        auth_model = self._transform_to_auth_model(authPermission)
        auth_token, refresh_token = self.adminService.issue_auth(challenge, client, auth_model)
        return auth_token, refresh_token

    def _transform_to_auth_model(self, permission: AuthPermission):
        ...
