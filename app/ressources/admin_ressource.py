from dataclasses import dataclass
from typing import Annotated, Any, List, Optional
from fastapi import Depends, Header, Query, Request, Response,HTTPException,status
from fastapi.responses import JSONResponse
from app.classes.celery import SchedulerModel, TaskType
from app.decorators.guards import CeleryTaskGuard
from app.services.assets_service import AssetService
from app.services.celery_service import BackgroundTaskService, CeleryService
from app.services.database_service import MongooseService
from app.services.security_service import JWTAuthService,SecurityService
from app.services.config_service import ConfigService
from app.utils.dependencies import get_admin_token, get_auth_permission, get_request_id
from app.container import InjectInMethod,Get
from app.definition._ressource import  Guard, PingService, UseGuard, UseHandler, UsePermission,BaseHTTPRessource,HTTPMethod,HTTPRessource, UsePipe, UseRoles,UseLimiter
from app.decorators.permissions import JWTRouteHTTPPermission
from app.classes.auth_permission import AuthPermission, Role,RoutePermission,AssetsPermission, TokensModel
from pydantic import BaseModel, RootModel,field_validator
from app.decorators.handlers import ServiceAvailabilityHandler, TortoiseHandler
from app.decorators.pipes import AuthClientPipe, AuthPermissionPipe, CeleryTaskPipe
from app.utils.validation import ipv4_validator
from slowapi.util import get_remote_address

ADMIN_PREFIX = 'admin'


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
@HTTPRessource(ADMIN_PREFIX)
class AdminRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self,configService:ConfigService,jwtAuthService:JWTAuthService,securityService:SecurityService):
        super().__init__(dependencies=[Depends(verify_admin_token)])
        self.configService = configService
        self.jwtAuthService = jwtAuthService
        self.securityService = securityService
        self.celeryService:CeleryService = Get(CeleryService)

    @UseLimiter(limit_value ='20/week')
    @BaseHTTPRessource.HTTPRoute('/blacklist/{client_id}',methods=[HTTPMethod.DELETE])
    def blacklist_tokens(self,client_id:str,request:Request ,authPermission=Depends(get_auth_permission)):
        # TODO verify if already blacklisted
        # TODO add to database 
        ...
    
    
    @UseLimiter(limit_value='1/day')
    @PingService([MongooseService,JWTAuthService])
    @BaseHTTPRessource.HTTPRoute('/invalidate-all/',methods=[HTTPMethod.DELETE])
    def invalidate_all_tokens(self,request:Request,authPermission=Depends(get_auth_permission)):
       
        self.jwtAuthService.set_generation_id(True)
        tokens = self._create_tokens(authPermission)
        return JSONResponse(status_code=status.HTTP_200_OK,content={"message":"Tokens successfully invalidated",
                                                                    "details": "Even if you're the admin old token wont be valid anymore",
                                                                    "tokens":tokens})
    
    @UseLimiter(limit_value='10/day')
    @UsePipe(AuthClientPipe)
    @PingService([MongooseService,JWTAuthService])
    @BaseHTTPRessource.HTTPRoute('/invalidate/{client}',methods=[HTTPMethod.DELETE],dependencies=None)
    def invalidate_tokens(self,request:Request,client:str,scope:str = Query(), authPermission=Depends(get_auth_permission)):
        ...

    @UseLimiter(limit_value='4/day')
    @PingService([MongooseService,JWTAuthService])
    @BaseHTTPRessource.HTTPRoute('/issue-auth/',methods=[HTTPMethod.GET])
    def issue_auth_token(self,authModel:AuthPermissionModel | List[AuthPermissionModel],request:Request, authPermission=Depends(get_auth_permission)):
        authModel:list[AuthPermissionModel] = authModel if isinstance(authModel,list) else [authModel]
        temp = self._create_tokens(authModel)
        return JSONResponse(status_code=status.HTTP_200_OK,content={"tokens":temp,"message":"Tokens successfully issued"})


    @UseLimiter(limit_value='1/day',key_func=get_remote_address)#VERIFY Once a month
    @UsePipe(AuthPermissionPipe)
    @PingService([JWTAuthService])
    @UseRoles([Role.REFRESH])
    @BaseHTTPRessource.HTTPRoute('/refresh-auth/',methods=[HTTPMethod.GET,HTTPMethod.POST],deprecated=True)# ERROR Security Error
    def refresh_auth_token(self,tokens:TokensModel, request:Request,authPermission=Depends(get_auth_permission)):
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
            # allowed_assets = token['allowed_assets']
            api_token  = self.securityService.generate_custom_api_key(issued_for)
            auth_token = self.jwtAuthService.encode_auth_token(allowed_routes,roles,issued_for)
            temp[issued_for]={"api_token":api_token,"auth_token":auth_token}
        return temp 