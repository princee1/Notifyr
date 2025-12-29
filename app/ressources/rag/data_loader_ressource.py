from typing import List
from fastapi import Depends, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from app.classes.auth_permission import AuthPermission
from app.container import InjectInMethod
from app.decorators.guards import UploadFilesGuard
from app.decorators.handlers import CostHandler, ServiceAvailabilityHandler, UploadFileHandler
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, IncludeRessource, UseGuard, UseHandler, UsePermission
from app.depends.dependencies import get_auth_permission
from app.services.config_service import ConfigService
from app.services.vault_service import VaultService
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import UseLimiter


@HTTPRessource('jobs',)
class JobArqRessource(BaseHTTPRessource):
    
    @InjectInMethod()
    def __init__(self,configService:ConfigService,vaultService:VaultService):
        super().__init__(None,None)



@IncludeRessource(JobArqRessource)
@UseHandler(ServiceAvailabilityHandler,CostHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('data-loader')
class DataLoaderRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,configService:ConfigService,vaultService:VaultService):
        super().__init__(None,None)
        self.configService = configService
        self.vaultService = vaultService

    @UseLimiter('5/hour')
    @UseHandler(UploadFileHandler)
    @UseGuard(UploadFilesGuard)
    @BaseHTTPRessource.HTTPRoute('/file/',methods=[HTTPMethod.POST])
    async def embed_files(self,files:List[UploadFile], request:Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        ...

    @UseLimiter('5/hour')
    @BaseHTTPRessource.HTTPRoute('/file/',methods=[HTTPMethod.POST])
    async def embed_web(self,request:Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        ...
    
    @UseLimiter('5/hour')
    @BaseHTTPRessource.HTTPRoute('/file/',methods=[HTTPMethod.POST])
    async def embed_api_data(self,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        ...

    