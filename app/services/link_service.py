from typing import Callable
from fastapi import HTTPException, Request,status
from app.classes.rsa import RSA
from app.definition._service import Service, ServiceClass
from app.models.link_model import LinkORM, QRCodeModel
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.reactive_service import ReactiveService
import qrcode as qr
import io
from app.services.security_service import SecurityService
from app.utils.helper import b64_encode, generateId
import aiohttp

from app.utils.tools import Cache

@ServiceClass
class LinkService(Service):
    
    def __init__(self,configService:ConfigService,redisService:RedisService,reactiveService:ReactiveService,securityService:SecurityService):
        super().__init__()
        
        self.configService = configService
        self.reactiveService = reactiveService
        self.redisService = redisService
        self.securityService = securityService

        self.BASE_URL:Callable[[str],str] = lambda v: self.configService.getenv('PROD_URL',"")+v
        self.IPINFO_API_KEY = self.configService['IPINFO_API_KEY']

    
    def build(self):
        ...

    async def generate_public_signature(self,link:LinkORM):
        rsa:RSA =  self.securityService.generate_key_pair()
        message= generateId(100)
        signature= ...

        await link.save()
        return signature,str(rsa.public_key)

    async def verify_public_signature(self,link:LinkORM,signature,public_key):
        ...

    def verify_safe_domain(self,domain:str):
        ...
    
    async def parse_info(self,request:Request,link_id:str,path:str,link_args):
        user_agent = request.headers.get('user-agent')
        client_ip = request.headers.get('x-forwarded-for')
        message_id = link_args.server_scoped.get("message_id",None)
        contact_id = link_args.server_scoped.get("contact_id",None)
        referrer = request.headers.get('referrer',None)

        ip_lookup = await self.ip_lookup(client_ip)
        loc:str = ip_lookup.get('loc',None)
        if loc == None:
            lat,long = None,None
        lat,long = loc.split(',')
        ip_data = {
            'country':ip_lookup.get('country',None),
            'get_lat':float(lat) if lat != None else None,
            'get_long':float(long) if long != None else None,
            'region':ip_lookup.get('region',None),
            'city':ip_lookup.get('city',None),
            'timezone':ip_lookup.get('timezone',None),
            'referrer':referrer,
        }

        return {
            'link_id':str(link_id),
            'user_agent':user_agent,
            'ip_address':client_ip,
            'link_path':path,
            'email_id':message_id,
            'contact_id':contact_id,
            **ip_data
        }
    
    #@Cache(10)
    async def ip_lookup(self,ip_address):
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.IPINFO_API_KEY}"
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"https://ipinfo.io/{ip_address}", headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        {}
            except aiohttp.ClientError as e:
                return {}
            except aiohttp.ConnectionTimeoutError as e:
                return {}
            except Exception:
                return {}

    async def get_server_well_know(self, link: LinkORM):

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

    async def generate_qr_code(self, full_url: str, qr_config:QRCodeModel):
        """
        Generate a QR code for the given URL with optional configuration.

        Args:
            full_url (str): The URL to encode in the QR code.
            qr_config (dict, optional): Configuration for the QR code (e.g., version, box_size, border).

        Returns:
            str: Base64-encoded QR code image.
        """

        qr_code = qr.QRCode(
            version=qr_config.version,
            box_size=qr_config.box_size,
            border=qr_config.border,
        )
        qr_code.add_data(full_url)
        qr_code.make(fit=True)

        img = qr_code.make_image(fill_color="black", back_color="white")
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)

        base64_img = b64_encode(img_io.read())
        return f'data:image/png;base64,{base64_img}'