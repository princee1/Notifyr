from fastapi import Request
from app.classes.auth_permission import MustHave, MustHaveRoleSuchAs, Role
from app.decorators.permissions import JWTAssetPermission, JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, PingService, UseLimiter, UsePermission, UseRoles, UseServiceLock
from app.services.assets_service import AssetService
from app.services import AmazonS3Service
from app.services.secret_service import HCVaultService



@HTTPRessource('webhooks')
class AssetWebhookRessource(BaseHTTPRessource):
    
    @UseLimiter(limit_value='1/day')
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.HEAD])
    def head(self,request:Request,):
        return

    


@UseRoles([Role.ASSETS])
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('assets',routers=[AssetWebhookRessource])
class AssetRessource(BaseHTTPRessource):
    
    @UseRoles(options=[MustHave(Role.ADMIN)])
    @PingService([HCVaultService])
    @UseServiceLock(HCVaultService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/generate-url/',methods=[HTTPMethod.GET])
    def generate_upload_url(self,request:Request,):
        ...
    
    @BaseHTTPRessource.HTTPRoute('/upload/')
    def upload_stream(self):

        ...
    @BaseHTTPRessource.HTTPRoute('download/')
    def download_stream(self):
        ...

    @UseRoles(options=[MustHave(Role.ADMIN)])
    @UsePermission(JWTAssetPermission)
    @PingService([AmazonS3Service])
    @UseServiceLock(AmazonS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/{template}',methods=[HTTPMethod.DELETE])
    def delete_asset(self,template:str):
        ...

    @PingService([AmazonS3Service])
    @UseRoles(roles=[Role.PUBLIC])
    @UsePermission(JWTAssetPermission)
    @UseServiceLock(AmazonS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/{template}',methods=[HTTPMethod.GET])
    def read_asset(self,template:str):
        ...
    

    
    
