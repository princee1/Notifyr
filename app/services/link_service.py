from typing import Callable, Literal
from urllib.parse import urlparse
from fastapi import HTTPException, Request, Response, status
from app.classes.rsa import RSA
from app.classes.template import HTMLTemplate
from app.definition._service import BaseService, BuildFailureError, Service, ServiceStatus
from app.models.link_model import LinkORM, QRCodeModel
from app.services.config_service import ConfigService
from app.services.database_service import RedisService, TortoiseConnectionService
from app.services.reactive_service import ReactiveService
import qrcode as qr
import io
from app.services.security_service import SecurityService
from app.utils.constant import SECONDS_IN_AN_HOUR
from app.utils.helper import b64_encode, generateId
import aiohttp
import json
from app.utils.tools import Cache, MyJSONCoder
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import re
from fastapi_cache.decorator import cache

def ip_lookup_key_builder(
    func: Callable,
    namespace: str = "",
    *,
    request: Request = None,
    response: Response = None,
    **kwargs,
):
    args = kwargs.get('args', [])
    return "-".join([
        namespace,
        func.__name__,
        args[1]
    ])



@Service()
class LinkService(BaseService):

    def __init__(self, configService: ConfigService, redisService: RedisService, reactiveService: ReactiveService, securityService: SecurityService,tortoiseConnService:TortoiseConnectionService):
        super().__init__()

        self.tortoiseConnService = tortoiseConnService
        self.configService = configService
        self.reactiveService = reactiveService
        self.redisService = redisService
        self.securityService = securityService

        self.BASE_URL: Callable[[str], str] = lambda v: self.configService.getenv(
            'PROD_URL', "")+v
        self.IPINFO_API_KEY = self.configService['IPINFO_API_KEY']

    def build(self,build_state=-1):
        ...

    def verify_dependency(self):
        if self.tortoiseConnService.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError

    async def generate_public_signature(self, link: LinkORM):
        rsa: RSA = self.securityService.generate_rsa_key_pair(512)
        nonce = generateId(50)
        message = {
            'domain': urlparse(link.link_url).hostname,
            'timestamp': link.created_at.isoformat(),
            'nonce': nonce
        }
        message = json.dumps(message)
        signature = rsa.sign_message(message)
        link.ownership_signature = signature
        link.ownership_nonce = nonce
        await link.save()
        return str(rsa.encrypted_public_key)

    async def verify_public_signature(self, link: LinkORM, public_key):

        rsa: RSA = self.securityService.generate_rsa_from_encrypted_keys(
            public_key=public_key[2:-1].encode())
        message = {
            'domain': urlparse(link.link_url).hostname,
            'timestamp': link.created_at.isoformat(),
            'nonce': link.ownership_nonce
        }
        message = json.dumps(message)
        return rsa.verify_signature(message, str(link.ownership_signature).encode())

    def verify_safe_domain(self, domain: str):
        ...

    async def parse_info(self, request: Request, link_id: str, path: str, link_query):
        if not path:
            path = None
        user_agent = request.headers.get('user-agent')
        client_ip = request.headers.get('x-forwarded-for')
        message_id = link_query.server_scoped.get("message_id", None)
        contact_id = link_query.server_scoped.get("contact_id", None)
        referrer = request.headers.get('referrer', None)

        ip_lookup: dict | None = await self.ip_lookup(client_ip)
        if ip_lookup != None:
            loc: str = ip_lookup.get('loc', None)
            if loc == None:
                lat, long = None, None
            else:
                lat, long = loc.split(',')
            ip_data = {
                'country': ip_lookup.get('country', None),
                'geo_lat': float(lat) if lat != None else None,
                'geo_long': float(long) if long != None else None,
                'region': ip_lookup.get('region', None),
                'city': ip_lookup.get('city', None),
                'timezone': ip_lookup.get('timezone', None),
                'referrer': referrer,
            }
        else:
            ip_data = {}

        return {
            'link_id': str(link_id),
            'user_agent': user_agent,
            'ip_address': client_ip,
            'link_path': path,
            'email_id': message_id,
            'contact_id': contact_id,
            **ip_data
        }

    @Cache('redis')(SECONDS_IN_AN_HOUR*2,coder=MyJSONCoder,key_builder=ip_lookup_key_builder, namespace="")
    async def ip_lookup(self, ip_address):
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
        parsed_url = urlparse(link.link_url)
        link_url = f"{parsed_url.scheme}://{parsed_url.netloc}/.well-known/notifyr/"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(link_url) as response:
                    if response.status == 200:
                        data: dict = await response.json()
                        return data['public-key']
                    else:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                                            "error": f"Failed to fetch well-known info, status code: {response.status}"})
            except aiohttp.ClientError as e:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
                                    "error": f"HTTP request failed: {str(e)}"})
            except KeyError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                                    "error": f"Failed to fetch well-known info"})

    async def generate_qr_code(self, full_url: str, qr_config: QRCodeModel):
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

    def create_tracking_pixel(self,format:Literal['html','raw_url'],email_id: str, contact_id: str = None, esp=None) -> str:
        """
        Generate a tracking pixel URL for the given email ID.

        Args:
            email_id (str): The email ID to associate with the tracking pixel.

        Returns:
            str: The full URL of the tracking pixel.
        """
        contact_id = '' if not contact_id else f'&contact_id={contact_id}'
        esp = f'&esp={esp}' if esp else 'Untracked Provider'
        tracking_path = f"/link/p/p.png/?message_id={email_id}{contact_id}{esp}"
        url = self.BASE_URL(tracking_path)
        if  format== 'html':
            return f"""
                    <!DOCTYPE html>
                    <html lang="en">
                    <head>
                        <meta charset="UTF-8">
                    </head>
                    <body>
                        <img src="{url}" width="1" height="1" style="display:none;" alt="" />
                    </body>
                    </html>
                    """
        else:
            return url

    def create_link_re(self, message_tracking_id, contact_id=None, add_params:dict={}) -> Callable[[str], str]:

        def callback(content: str) -> str:
            esp = add_params.get('esp',None)
            if content == None:
                return None

            def _replace_link(match):
                original_url = match.group(0)
                parsed_url = urlparse(original_url)
                redirect_url = original_url

                if parsed_url.netloc == urlparse(self.BASE_URL("")).netloc:
                    # If the netloc matches the base URL, use only the path and query
                    redirect_url = urlunparse(
                        ("", "", parsed_url.path, parsed_url.params, parsed_url.query, ""))

                # Construct the new tracking URL
                query_params = {}
                if contact_id:
                    query_params['contact_id'] = contact_id

                if add_params:
                    query_params.update(add_params)

                query_params.update({
                    "message_id": message_tracking_id,
                    "r": redirect_url
                })
                tracking_url = self.BASE_URL(
                    f"/link/t/?{urlencode(query_params,encoding='utf-8')}")
                # Debugging the tracking URL
                return tracking_url

            # Regex to match URLs in the content
            url_pattern = r'https?://[^\s"<>()]+'
            new_content = re.sub(url_pattern, _replace_link, content)
            return new_content

        return callback

    def generate_html(self, img_data):
        html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>QR Code</title>
            </head>
            <body>
                <h1>QR Code</h1>
                <img src="{img_data}" alt="QR Code">
            </body>
            </html>
            """

        return html_content
