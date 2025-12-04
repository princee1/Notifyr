import asyncio
import hashlib
import hmac
import json
from typing import Any, Tuple
import requests
import aiohttp
from app.definition._service import BaseMiniService, MiniService
from app.interface.webhook_adapter import WebhookAdapterInterface
from app.models.webhook_model import AuthConfig, HTTPWebhookModel, SignatureConfig
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.profile_service import ProfileMiniService


@MiniService()
class HTTPWebhookMiniService(BaseMiniService,WebhookAdapterInterface):

    def __init__(self,profileMiniService:ProfileMiniService[HTTPWebhookModel],configService:ConfigService,redisService:RedisService):
        self.depService = profileMiniService
        super().__init__(profileMiniService,None)
        WebhookAdapterInterface.__init__(self,)
        self.configService = configService
        self.redisService = redisService

    @property
    def model(self):
        return self.depService.model

    async def close(self):
        await self.client_async.aclose()

    def build(self, build_state = ...):
        
        self.client_async = aiohttp.ClientSession(
            timeout=self.model.timeout,
            )
        self.client = requests.Session()
        

    @staticmethod
    def json_bytes(payload: Any) -> bytes:
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    
    @staticmethod
    def hmac_signature(secret: str, body: bytes,algo:str) -> str:
        mac = hmac.new(secret.encode(), body, hashlib.sha256)
        return "sha256=" + mac.hexdigest()
    

    def set_encoding_data(self,payload,body_bytes,headers:dict):
        """Return kwargs for httpx/requests request depending on encoding. May mutate headers for content-type."""
        if self.model.encoding == "json":
            return {"content": body_bytes}
        elif self.model.encoding == "form":
            # for form encoding prefer sending data when payload is a dict
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
            if isinstance(payload, dict):
                return {"data": payload}
            return {"content": body_bytes}
        elif self.model.encoding == "raw":
            return {"content": body_bytes}
        else:
            return {"content": body_bytes}

        
    def sign(self,headers:dict,body_bytes,cred:dict):
        config:SignatureConfig = cred.get('signature_config',None)
        if not config:
            return 
        sig_header = config.get('header_name') or 'X-Webhook-Signature'
        secrets = config.get('secret')
        algo = config.get("algo")
        headers[sig_header] = self.hmac_signature(secrets, body_bytes,algo)
    

    @WebhookAdapterInterface.batch
    @WebhookAdapterInterface.retry
    async def deliver_async(self,payload: Any,event_type:str='event') -> Tuple[int, bytes]: 
        method, headers, request_kwargs, auth, url = self.prepare_request(payload, event_type)
        webhook_handler = self.client_async.request(method, url,auth=auth,headers=headers,params=self.model.params,timeout=self.model.timeout, **request_kwargs)
        if self.model.send_and_wait:
            resp = await webhook_handler
            return resp.status, resp.content
        
        asyncio.create_task(webhook_handler)
        return 201,{}

    @WebhookAdapterInterface.retry
    def deliver(self,payload: Any,event_type:str='event') -> tuple[int, bytes]:
        method, headers, request_kwargs, auth, url = self.prepare_request(payload, event_type)

        resp = self.client.request(method, url, auth=auth, headers=headers, params=self.model.params, timeout=self.model.timeout, **request_kwargs)
        return resp.status_code, resp.content

    def prepare_request(self, payload, event_type):
        delivery_id: str = self.generate_delivery_id()
        body_bytes = self.json_bytes(payload)
        method = self.model.method

        headers = {"Content-Type": "application/json","X-Delivery-Id": delivery_id,"X-Event-Type": event_type,}

        cred= self.depService.credentials.to_plain()

        headers.update(self.model.headers)
        headers.update(cred.get('secret_headers',{}))

        self.sign(headers,body_bytes,cred)
        request_kwargs = self.set_encoding_data(payload,body_bytes,headers)

        auth:AuthConfig = cred.get('auth',None)
        auth = tuple(auth.values()) if auth else None
        url = cred['url']
        return method,headers,request_kwargs,auth,url


