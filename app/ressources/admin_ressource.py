from typing import Annotated, Any
from fastapi import Depends, Header, Request, Response,HTTPException,status
from services.config_service import ConfigService
from utils.dependencies import get_admin_token, get_bearer_token, get_client_ip
from container import InjectInMethod,Get
from definition._ressource import Guard, UseGuard, UsePermission,BaseRessource,HTTPMethod,Ressource
from decorators.permissions import JWTHTTPRoutePermission

ADMIN_PREFIX = 'admin'
ADMIN_STARTS_WITH = '_admin'

async def verify_admin_token(x_admin_token: Annotated[str, Header()]):
    configService:ConfigService = Get(ConfigService)
    
    if x_admin_token == None or x_admin_token != configService.ADMIN_KEY:
        raise HTTPException(status_code=403, detail="X-Admin-Token header invalid")


@Ressource(ADMIN_PREFIX)
@UsePermission(JWTHTTPRoutePermission)
class AdminRessource(BaseRessource):

    @InjectInMethod
    def __init__(self,configService:ConfigService):
        super().__init__(dependencies=[Depends(verify_admin_token)])
        self.configService = configService
    

    @BaseRessource.HTTPRoute('/',HTTPMethod.GET)
    def _api_admin_page(self,request:Request, response:Response,):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)