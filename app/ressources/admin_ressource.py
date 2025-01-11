from typing import Any
from fastapi import Depends, Request, Response,HTTPException,status
from services.config_service import ConfigService
from utils.dependencies import get_admin_token, get_bearer_token, get_client_ip
from container import InjectInMethod,Get
from definition._ressource import Guard, UseGuard, UsePermission,Ressource,HTTPMethod


ADMIN_PREFIX = 'admin'
ADMIN_STARTS_WITH = '_admin'


class AdminRessource(Ressource):

    @InjectInMethod
    def __init__(self,configService:ConfigService):
        super().__init__(ADMIN_PREFIX)
        self.configService = configService
    
    @UsePermission()
    @UseGuard()
    @Ressource.HTTPRoute('/',HTTPMethod.GET)
    def _api_admin_page(self,request:Request, response:Response,token_= Depends(get_bearer_token), client_ip_=Depends(get_client_ip),admin_=Depends(get_admin_token())):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)