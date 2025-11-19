import hashlib
import hmac
import json
from typing import Any

from aiohttp_retry import Tuple
import httpx
from app.definition._service import BaseMiniService
from app.interface.webhook_adapter import WebhookAdapterInterface
from app.models.webhook_model import AuthConfig, HTTPWebhookModel, SignatureConfig
from app.services.profile_service import ProfileMiniService


class HTTPWebhookMiniService(BaseMiniService,WebhookAdapterInterface):

    def __init__(self,profileMiniService:ProfileMiniService[HTTPWebhookModel],):
        self.depService = profileMiniService
        super().__init__(profileMiniService,None)

    @property
    def model(self):
        return self.depService.model

    async def close(self):
        await self.client.aclose()

    def build(self, build_state = ...):
        
        self.client = httpx.AsyncClient(
            timeout=self.model.timeout,
            http2=self.model.http2
            )

    @staticmethod
    def json_bytes(payload: Any) -> bytes:
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    
    @staticmethod
    def hmac_signature(secret: str, body: bytes) -> str:
        mac = hmac.new(secret.encode(), body, hashlib.sha256)
        return "sha256=" + mac.hexdigest()
    

    def set_encoding_data(self,payload,body_bytes):
        content_kwargs = {}
        if self.model.encoding == "json":
            content_kwargs["content"] = body_bytes
        elif self.model.encoding == "form":
            # if payload is dict, send as form fields
            if isinstance(payload, dict):
                content_kwargs["data"] = payload
            else:
                content_kwargs["content"] = body_bytes
            content_kwargs["Content-Type"] = "application/x-www-form-urlencoded"
        elif self.model.encoding == "raw":
            content_kwargs["content"] = body_bytes
        else:
            content_kwargs["content"] = body_bytes

        
    def sign(self,headers:dict,body_bytes,config:dict):
        config:SignatureConfig = config.get('signature_config',None)
        if not config: return 
        sig_header = config.get('header_name')
        algo = config.get("algo")
        secrets = config.get('secret')
        headers[sig_header] = self.hmac_signature(secrets, body_bytes, algo=algo)
    

    async def deliver(self,payload: Any,event_type:str='event') -> Tuple[int, bytes]:

        delivery_id: str = self.generate_delivery_id()
        body_bytes = self.json_bytes(payload)
        method = self.model.method

        headers = {"Content-Type": "application/json","X-Delivery-Id": delivery_id,"X-Event-Type": event_type,}

        cred= self.depService.credentials.to_plain()

        headers.update(self.model.headers)
        headers.update(cred.get('secret_headers',{}))

        self.sign(headers,body_bytes,cred)
        request_kwargs = self.set_encoding_data(payload,body_bytes)
        
        auth:AuthConfig = cred.get('auth',None)
        auth = tuple(auth.values()) if auth else None
        url = cred['url']
        
        resp = await self.client.request(method, url,auth=auth,headers=headers,params=self.model.params,timeout=self.model.timeout, **request_kwargs)
       
        return resp.status_code, resp.content


