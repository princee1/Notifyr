from dataclasses import dataclass
from typing import Annotated, Any, List, Optional
from fastapi import Depends, Header, Query, Request, Response,HTTPException,status
from fastapi.responses import JSONResponse
from app.decorators.guards import RefreshTokenGuard
from app.decorators.my_depends import get_client, get_group
from app.models.security_model import ClientModel, ClientORM, GroupClientORM, GroupModel
from app.services.admin_service import AdminService
from app.services.celery_service import CeleryService
from app.services.security_service import JWTAuthService,SecurityService
from app.services.config_service import ConfigService
from app.utils.constant import ConfigAppConstant
from app.utils.dependencies import  get_auth_permission, get_request_id
from app.container import InjectInMethod,Get
from app.definition._ressource import PingService, UseGuard, UseHandler, UsePermission,BaseHTTPRessource,HTTPMethod,HTTPRessource, UsePipe, UseRoles,UseLimiter
from app.decorators.permissions import JWTRouteHTTPPermission
from app.classes.auth_permission import AuthPermission, Role,RoutePermission,AssetsPermission, TokensModel
from pydantic import BaseModel, RootModel,field_validator
from app.decorators.handlers import ServiceAvailabilityHandler, TortoiseHandler
from app.decorators.pipes import  AuthPermissionPipe, ForceClientPipe, ForceGroupPipe, RefreshTokenPipe
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
    
class GenerationModel(BaseModel):
    generation_id:str
    

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
    async def create_client(self,client:ClientModel, authPermission=Depends(get_auth_permission)):
        name = client.client_name
        scope = client.scope
        group_id = client.group_id
        client = await ClientORM.create(client_name= name,client_scope=scope,group=group_id)
        return JSONResponse(status_code=status.HTTP_201_CREATED,content={"message":"Client successfully created","client":client})
    
    @UsePipe(ForceGroupPipe)
    @UsePipe(ForceClientPipe)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.PUT])
    async def add_client_to_group(self,client:Annotated[ClientORM,Depends(get_client)],group:Annotated[GroupClientORM,Depends(get_group)]):
        client.group = group
        await client.save()
        return JSONResponse(status_code=status.HTTP_200_OK,content={"message":"Client successfully added to group","client":client})

    @UsePipe(ForceClientPipe)
    @BaseHTTPRessource.Delete('/')
    async def delete_client(self,client:Annotated[ClientORM,Depends(get_client)],authPermission=Depends(get_auth_permission)):
        await client.delete()
        return JSONResponse(status_code=status.HTTP_200_OK,content={"message":"Client successfully deleted","client":client})

    @BaseHTTPRessource.Get('/')
    async def get_all_client(self,authPermission=Depends(get_auth_permission)):
        ...
    
    @BaseHTTPRessource.Post('/group/')
    async def create_group(self, group:GroupModel ,authPermission=Depends(get_auth_permission)):
        group_name = group.group_name
        group = await GroupClientORM.create(group_name=group_name)
        return JSONResponse(status_code=status.HTTP_201_CREATED,content={"message":"Group successfully created","group":group})
        
    @UsePipe(ForceGroupPipe)
    @BaseHTTPRessource.Delete('/group/')
    async def delete_group(self,group:Annotated[GroupClientORM,Depends(get_group)],authPermission=Depends(get_auth_permission)):
        await group.delete()
        return JSONResponse(status_code=status.HTTP_200_OK,content={"message":"Group successfully deleted","group":group})

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
    def blacklist_tokens(self,group:Annotated[GroupClientORM,get_group],client:Annotated[ClientORM,Depends(get_client)], request:Request ,authPermission=Depends(get_auth_permission)):
        # TODO verify if already blacklisted
        # TODO add to database 
        ...
    
    @UseLimiter(limit_value='1/day')
    @PingService([JWTAuthService])
    @BaseHTTPRessource.HTTPRoute('/revoke-all/',methods=[HTTPMethod.DELETE])
    def revoke_all_tokens(self,request:Request,authPermission=Depends(get_auth_permission)):
        old_generation_id = self.configService.config_json_app[ConfigAppConstant.GENERATION_ID_KEY]
        self.jwtAuthService.set_generation_id(True)
        new_generation_id= self.configService.config_json_app[ConfigAppConstant.GENERATION_ID_KEY]
        tokens = self._create_tokens(authPermission)
        return JSONResponse(status_code=status.HTTP_200_OK,content={"message":"Tokens successfully invalidated",
                                                                    "details": "Even if you're the admin old token wont be valid anymore",
                                                                    "tokens":tokens,
                                                                    "old_generation_id":old_generation_id,
                                                                    "new_generation_id":new_generation_id}) 
    
    @UseLimiter(limit_value='1/day')
    @PingService([JWTAuthService])
    @BaseHTTPRessource.HTTPRoute('/unrevoke-all/',methods=[HTTPMethod.POST])
    def unrevoke_all_tokens(self,request:Request,generation:GenerationModel, authPermission=Depends(get_auth_permission)):
        old_generation_id = self.configService.config_json_app[ConfigAppConstant.GENERATION_ID_KEY]
        self.jwtAuthService.set_generation_id(True)
        new_generation_id = generation.generation_id
        self.configService.config_json_app[ConfigAppConstant.GENERATION_ID_KEY] = new_generation_id
        self.configService.config_json_app.save()
        tokens = self._create_tokens(authPermission)
        return JSONResponse(status_code=status.HTTP_200_OK,content={"message":"Tokens successfully invalidated",
                                                                    "details": "Even if you're the admin old token wont be valid anymore",
                                                                    "tokens":tokens,
                                                                    "old_generation_id":old_generation_id,
                                                                    "new_generation_id":new_generation_id}) 

    @UseLimiter(limit_value='10/day')
    @UsePipe(ForceClientPipe)
    @PingService([JWTAuthService])
    @BaseHTTPRessource.HTTPRoute('/invalidate/{client_id}',methods=[HTTPMethod.DELETE],dependencies=None)
    def revoke_tokens(self,request:Request,client:Annotated[ClientORM,Depends(get_client)], authPermission=Depends(get_auth_permission)):
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