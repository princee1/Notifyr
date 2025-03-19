from dataclasses import dataclass
from typing import Annotated, Any, List, Optional
from fastapi import Depends, Header, Query, Request, Response,HTTPException,status
from fastapi.responses import JSONResponse
from app.decorators.guards import RefreshTokenGuard
from app.decorators.my_depends import get_client, get_group
from app.models.security_model import ClientORM, GroupORM
from app.services.admin_service import AdminService
from app.services.celery_service import CeleryService
from app.services.security_service import JWTAuthService,SecurityService
from app.services.config_service import ConfigService
from app.utils.dependencies import  get_auth_permission, get_request_id
from app.container import InjectInMethod,Get
from app.definition._ressource import PingService, UseGuard, UseHandler, UsePermission,BaseHTTPRessource,HTTPMethod,HTTPRessource, UsePipe, UseRoles,UseLimiter
from app.decorators.permissions import JWTRouteHTTPPermission
from app.classes.auth_permission import AuthPermission, Role,RoutePermission,AssetsPermission, TokensModel
from pydantic import BaseModel, RootModel,field_validator
from app.decorators.handlers import ServiceAvailabilityHandler, TortoiseHandler
from app.decorators.pipes import  AuthPermissionPipe, ForceClientPipe, RefreshTokenPipe
from app.utils.validation import ipv4_validator
from slowapi.util import get_remote_address

ADMIN_PREFIX = 'admin'
CLIENT_PREFIX = 'client'


async def verify_admin_token(x_admin_token: Annotated[str, Header()]):
    configService:ConfigService = Get(ConfigService)
    
    if x_admin_token == None or x_admin_token != configService.ADMIN_KEY:
        raise HTTPException(status_code=403, detail="X-Admin-Token header invalid")

class AuthPermissionModel(BaseModel):
    issued_for:str
    allowed_routes:dict[str,RoutePermission] 
    allowed_assets:Optional[dict[str,AssetsPermission]]
    roles:Optional[list[Role]] = [Role.PUBLIC.value]

    @field_validator('issued_for')
    def check_issued_for(cls,issued_for:str):
        if not ipv4_validator(issued_for):
            raise ValueError('Invalid IP Address')
        return issued_for
    

@UseHandler(TortoiseHandler)   
@UseRoles([Role.ADMIN])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler)
@HTTPRessource(CLIENT_PREFIX)
class ClientRessource(BaseHTTPRessource):
    
    @InjectInMethod
    def __init__(self,configService:ConfigService,securityService:SecurityService,jwtAuthService:JWTAuthService,adminService:AdminService):
        super().__init__(dependencies=[Depends(verify_admin_token)])
        self.configService = configService
        self.securityService = securityService
        self.jwtAuthService = jwtAuthService
        self.adminService = adminService

    
    @BaseHTTPRessource.Post('/')
    async def create_client(self,authPermission=Depends(get_auth_permission)):
        ...
    
    @UsePipe(ForceClientPipe)
    @BaseHTTPRessource.Delete('/')
    async def delete_client(self,client:Annotated[ClientORM,Depends(get_client)],authPermission=Depends(get_auth_permission)):
        await client.delete()
        return JSONResponse(status_code=status.HTTP_200_OK,content={"message":"Client successfully deleted","client":client})

    @BaseHTTPRessource.Get('/')
    async def get_all_client(self,authPermission=Depends(get_auth_permission)):
        ...
    
    @BaseHTTPRessource.Post('/group/')
    async def create_group(self, group:Annotated[GroupORM,Depends(get_group)],authPermission=Depends(get_auth_permission)):
        if group == None:
            ...
        ...
    
    @BaseHTTPRessource.Delete('/group/')
    async def delete_group(self,authPermission=Depends(get_auth_permission)):
        ...

    @BaseHTTPRessource.Get('/group/')
    async def get_all_group(self,authPermission=Depends(get_auth_permission)):
        ...


    
@UseHandler(TortoiseHandler)   
@UseRoles([Role.ADMIN])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler)
@HTTPRessource(ADMIN_PREFIX,routers=[ClientRessource])
class AdminRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self,configService:ConfigService,jwtAuthService:JWTAuthService,securityService:SecurityService,adminService:AdminService):
        super().__init__(dependencies=[Depends(verify_admin_token)])
        self.configService = configService
        self.jwtAuthService = jwtAuthService
        self.securityService = securityService
        self.adminService = adminService
        self.celeryService:CeleryService = Get(CeleryService)

    @UseLimiter(limit_value ='20/week')
    @BaseHTTPRessource.HTTPRoute('/blacklist/{client_id}',methods=[HTTPMethod.DELETE,HTTPMethod.POST])
    def blacklist_tokens(self,group:Annotated[GroupORM,get_group],client:Annotated[ClientORM,Depends(get_client)], request:Request ,authPermission=Depends(get_auth_permission)):
        # TODO verify if already blacklisted
        # TODO add to database 
        ...
    
    @UseLimiter(limit_value='1/day')
    @PingService([JWTAuthService])
    @BaseHTTPRessource.HTTPRoute('/invalidate-all/',methods=[HTTPMethod.DELETE])
    def invalidate_all_tokens(self,request:Request,authPermission=Depends(get_auth_permission)):
        self.jwtAuthService.set_generation_id(True)
        tokens = self._create_tokens(authPermission)
        return JSONResponse(status_code=status.HTTP_200_OK,content={"message":"Tokens successfully invalidated",
                                                                    "details": "Even if you're the admin old token wont be valid anymore",
                                                                    "tokens":tokens})
    
    @UseLimiter(limit_value='10/day')
    @UsePipe(ForceClientPipe)
    @PingService([JWTAuthService])
    @BaseHTTPRessource.HTTPRoute('/invalidate/{client_id}',methods=[HTTPMethod.DELETE],dependencies=None)
    def invalidate_tokens(self,request:Request,client:Annotated[ClientORM,Depends(get_client)], authPermission=Depends(get_auth_permission)):
        ...

    @UseLimiter(limit_value='4/day')
    @UsePipe(ForceClientPipe)
    @PingService([JWTAuthService])
    @BaseHTTPRessource.HTTPRoute('/issue-auth/{client_id}',methods=[HTTPMethod.GET])
    def issue_auth_token(self,client:Annotated[ClientORM,Depends(get_client)], authModel:AuthPermissionModel,request:Request, authPermission=Depends(get_auth_permission)):
        authModel:list[AuthPermissionModel] = authModel if isinstance(authModel,list) else [authModel]
        temp = self._create_tokens(authModel)
        return JSONResponse(status_code=status.HTTP_200_OK,content={"tokens":temp,"message":"Tokens successfully issued"})


    @UseLimiter(limit_value='1/day',key_func=get_remote_address)#VERIFY Once a month
    @UsePipe(AuthPermissionPipe)
    @UseGuard(RefreshTokenGuard)
    @PingService([JWTAuthService])
    @UsePipe(ForceClientPipe,RefreshTokenPipe)
    @UseRoles(exclude=[Role.ADMIN],include=[Role.REFRESH])
    @BaseHTTPRessource.HTTPRoute('/refresh-auth/{client_id}',methods=[HTTPMethod.GET,HTTPMethod.POST],deprecated=True)# ERROR Security Error
    def refresh_auth_token(self,tokens:TokensModel,client:Annotated[ClientORM,Depends(get_client)], request:Request,authPermission=Depends(get_auth_permission)):
        tokens:list[AuthPermission] = tokens
        tokens = self._create_tokens(tokens)
        return JSONResponse(status_code=status.HTTP_200_OK,content={'tokens':tokens ,"message":"Tokens successfully invalidated"})
    

    def _create_tokens(self,tokens):
        temp ={}
        for token in tokens:
            issued_for = token['issued_for']
            allowed_routes = token['allowed_routes']
            roles = token['roles']
            public = Role.PUBLIC.value
            if public not in roles:
                roles.append(public)
            allowed_assets = token['allowed_assets']
            api_token  = self.securityService.generate_custom_api_key(issued_for)
            auth_token = self.jwtAuthService.encode_auth_token(allowed_routes,roles,issued_for,allowed_assets)
            temp[issued_for]={"api_token":api_token,"auth_token":auth_token}
        return temp 