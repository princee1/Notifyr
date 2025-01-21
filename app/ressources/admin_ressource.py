from dataclasses import dataclass
from typing import Annotated, Any, Optional
from fastapi import Depends, Header, Request, Response,HTTPException,status
from fastapi.responses import JSONResponse
from services.assets_service import AssetService
from services.security_service import JWTAuthService,SecurityService
from services.config_service import ConfigService
from utils.dependencies import get_admin_token, get_auth_permission, get_bearer_token, get_client_ip
from container import InjectInMethod,Get
from definition._ressource import Guard, UseGuard, UseHandler, UsePermission,BaseRessource,HTTPMethod,Ressource
from decorators.permissions import JWTRouteHTTPPermission
from classes.permission import AuthPermission,RoutePermission,AssetsPermission
from pydantic import BaseModel, RootModel,field_validator
from decorators.handlers import ServiceAvailabilityHandler
from utils.validation import ipv4_validator


ADMIN_PREFIX = 'admin'
ADMIN_STARTS_WITH = '_admin'

async def verify_admin_token(x_admin_token: Annotated[str, Header()]):
    configService:ConfigService = Get(ConfigService)
    
    if x_admin_token == None or x_admin_token != configService.ADMIN_KEY:
        raise HTTPException(status_code=403, detail="X-Admin-Token header invalid")

@dataclass
class AuthPermissionModel(BaseModel):
    issued_for:str
    allowed_routes:dict[str,RoutePermission] 
    allowed_assets:Optional[dict[str,AssetsPermission]]

    @field_validator('issued_for')
    def check_issued_for(cls,issued_for:str):
        if not ipv4_validator(issued_for):
            raise ValueError('Invalid IP Address')
        return issued_for


@Ressource(ADMIN_PREFIX)
@UsePermission(JWTRouteHTTPPermission)
class AdminRessource(BaseRessource):

    @InjectInMethod
    def __init__(self,configService:ConfigService,jwtAuthService:JWTAuthService,securityService:SecurityService,assetService:AssetService):
        super().__init__(dependencies=[Depends(verify_admin_token)])
        self.configService = configService
        self.jwtAuthService = jwtAuthService
        self.securityService = securityService
        self.assetService = assetService

    
    @UseHandler(ServiceAvailabilityHandler)
    @BaseRessource.HTTPRoute('/invalidate/',methods=[HTTPMethod.DELETE])
    def invalidate_tokens(self,authPermission=Depends(get_auth_permission)):
        self.jwtAuthService.pingService()
        self.jwtAuthService.set_generation_id(True)
        return JSONResponse(status_code=status.HTTP_200_OK,content={"message":"Tokens successfully invalidated"})


    @UseHandler(ServiceAvailabilityHandler)
    @BaseRessource.HTTPRoute('/issue-auth/',methods=[HTTPMethod.GET])
    def issue_token(self,authModel:AuthPermissionModel,authPermission=Depends(get_auth_permission)):
        self.jwtAuthService.pingService()

        issued_for = authModel.issued_for
        allowed_routes = authModel.allowed_routes
        #allowed_assets = authModel.allowed_assets
        # TODO validation
        api_token  = self.securityService.generate_custom_api_key(issued_for)
        auth_token = self.jwtAuthService.encode_auth_token(allowed_routes,issued_for)
        return JSONResponse(status_code=status.HTTP_200_OK,content={"api_token":api_token,"auth_token":auth_token})
    

    