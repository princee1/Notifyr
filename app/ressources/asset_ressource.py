from io import BytesIO
from aiohttp_retry import List
from fastapi import File, Request, UploadFile
from app.classes.auth_permission import MustHave, MustHaveRoleSuchAs, Role
from app.container import InjectInMethod
from app.decorators.permissions import JWTAssetPermission, JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, PingService, UseLimiter, UsePermission, UseRoles, UseServiceLock
from app.services.assets_service import AssetService
from app.services import AmazonS3Service
from app.services.secret_service import HCVaultService

@UseRoles([Role.ASSETS])
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('assets')
class AssetRessource(BaseHTTPRessource):
    

    @InjectInMethod()
    def __init__(self, assetService: AssetService, amazonS3Service: AmazonS3Service, hcVaultService: HCVaultService):
        super().__init__()
        self.assetService: AssetService = assetService
        self.amazonS3Service: AmazonS3Service = amazonS3Service
        self.hcVaultService: HCVaultService = hcVaultService

    @UseRoles(options=[MustHave(Role.ADMIN)])
    @PingService([HCVaultService])
    @UseServiceLock(HCVaultService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/generate-url/',methods=[HTTPMethod.GET,HTTPMethod.PUT])
    def generate_url(self,request:Request,):
        method = request.method
        self.amazonS3Service.generate_presigned_url(method=method)
    
    @UsePermission(JWTAssetPermission)
    @UseRoles(options=[MustHave(Role.ADMIN)])
    @PingService([AmazonS3Service])
    @UseServiceLock(AmazonS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/upload/')
    async def upload_stream(self,request:Request,files: List[UploadFile] = File(...)):
        for file in files:
            file_bytes = await file.read()
            file_io = BytesIO(file_bytes)
            await self.amazonS3Service.upload_object(file.filename,file_io)

    @UsePermission(JWTAssetPermission)
    @PingService([AmazonS3Service])
    @UseServiceLock(AmazonS3Service,AssetService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('download/{template}',methods=[HTTPMethod.GET])
    async def download_stream(self,request:Request,template:str):
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
    

    
    
