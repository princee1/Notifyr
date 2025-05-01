from typing import Callable
from app.definition._service import Service, ServiceClass
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.reactive_service import ReactiveService
import qrcode as qr
import io
from app.utils.helper import b64_encode

@ServiceClass
class LinkService(Service):
    
    def __init__(self,configService:ConfigService,redisService:RedisService,reactiveService:ReactiveService):
        super().__init__()
        self.configService = configService
        self.reactiveService = reactiveService
        self.redisService = redisService

        self.BASE_URL:Callable[[str],str] = lambda v: self.configService.getenv('PROD_URL',"")+v
    
    def build(self):
        ...
    

    def verify_safe_domain(self,):
        ...
    
    async def verify_server_well_know(self,):
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