from typing import Callable
from fastapi import HTTPException,status
from app.definition._service import Service, ServiceClass
from app.models.link_model import LinkORM
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.reactive_service import ReactiveService
import qrcode as qr
import io
from app.services.security_service import SecurityService
from app.utils.helper import b64_encode
import aiohttp

@ServiceClass
class LinkService(Service):
    
    def __init__(self,configService:ConfigService,redisService:RedisService,reactiveService:ReactiveService,securityService:SecurityService):
        super().__init__()
        
        self.configService = configService
        self.reactiveService = reactiveService
        self.redisService = redisService
        self.securityService: SecurityService = securityService

        self.BASE_URL:Callable[[str],str] = lambda v: self.configService.getenv('PROD_URL',"")+v
    
    def build(self):
        ...
    

    def verify_safe_domain(self,):
        ...
    
    async def verify_server_well_know(self, link: LinkORM):

        link_url = link.link_url
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(link_url) as response:
                    if response.status == 200:
                        data = await response.json()
                    else:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": f"Failed to fetch well-known info, status code: {response.status}"})
            except aiohttp.ClientError as e:
                return  HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail={"error": f"HTTP request failed: {str(e)}"})
        
        ...

    async def generate_qr_code(self,):
        
        qr_code = qr.QRCode(
            version = 1,

        )
        img_io = io.BytesIO()
        qr.save(img_io, 'PNG')
        img_io.seek(0)

        base64_img = b64_encode(img_io.read())
        return f'data:image/png;base64,{base64_img}'