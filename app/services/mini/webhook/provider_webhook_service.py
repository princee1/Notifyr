import asyncio
import hashlib
import hmac
import json
from typing import Any, Dict, Optional, TypedDict
import aiohttp
from aiohttp_retry import Tuple
import requests
from app.definition._service import BaseMiniService, LinkDep, MiniService
from app.interface.webhook_adapter import WebhookAdapterInterface
from app.models.odm.outbound_model import AuthConfig
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from app.services.profile_service import ProfileMiniService
from app.models.odm.webhook_model import DiscordWebhookModel, HTTPWebhookModel, MakeHTTPWebhookModel, SignatureConfig, SlackHTTPWebhookModel, ZapierHTTPWebhookModel
from discord_webhook import DiscordEmbed,DiscordWebhook,AsyncDiscordWebhook


@MiniService(links=[LinkDep(ProfileMiniService,build_follow_dep=True)])
class HTTPWebhookMiniService(BaseMiniService,WebhookAdapterInterface):
    def __init__(self, profileMiniService:ProfileMiniService[HTTPWebhookModel], configService:ConfigService, redisService:RedisService):
        self.depService = profileMiniService
        super().__init__(profileMiniService,None)
        self.configService = configService
        self.redisService = redisService        
        WebhookAdapterInterface.__init__(self)

    @WebhookAdapterInterface.batch
    @WebhookAdapterInterface.retry
    async def deliver_async(self, payload:Any, event_type:str = 'event'):
        method, headers, request_kwargs, auth, url = self.prepare_request(payload, event_type)
        webhook_handler = self.client_async.request(method, url,auth=auth,headers=headers,params=self.model.params,timeout=self.model.timeout, **request_kwargs)
        if self.model.send_and_wait:
            resp = await webhook_handler
            return resp.status, resp.content
        
        asyncio.create_task(webhook_handler)
        return 201,{}
    
    @WebhookAdapterInterface.retry
    async def deliver(self, payload:str, event_type:str = 'event'):
        method, headers, request_kwargs, auth, url = self.prepare_request(payload, event_type)

        resp = self.client.request(method, url, auth=auth, headers=headers, params=self.model.params, timeout=self.model.timeout, **request_kwargs)
        return resp.status_code, resp.content
    
    @staticmethod
    def generate_delivery_id():
        return WebhookAdapterInterface.generate_delivery_id()
    
    @property
    def model(self):
        return self.depService.model

    async def close(self):
        await self.client_async.close()

    def build(self, build_state = ...):
        self.client_async = aiohttp.ClientSession(timeout=self.model.timeout,)
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
    
    def prepare_request(self, payload, event_type):
        delivery_id: str = self.generate_delivery_id()
        body_bytes = self.json_bytes(payload)
        method = self.model.method

        headers = {"Content-Type": "application/json","X-Event-Type": event_type,}
        
        if delivery_id:
            headers.update({"X-Delivery-Id": delivery_id})

        cred= self.depService.credentials.to_plain()

        headers.update(self.model.headers)
        headers.update(cred.get('secret_headers',{}))

        self.sign(headers,body_bytes,cred)
        request_kwargs = self.set_encoding_data(payload,body_bytes,headers)

        auth:AuthConfig = cred.get('auth',None)
        auth = tuple(auth.values()) if auth else None
        url = cred['url']
        return method,headers,request_kwargs,auth,url


@MiniService()
class DiscordWebhookMiniService(BaseMiniService,WebhookAdapterInterface):
    
    class DiscordBody(TypedDict):
        embeds:list[DiscordEmbed | Dict]
        attachements:list[dict[str,Any]]
        files:Dict[str, Tuple[Optional[str], bytes| str]]

    def __init__(self,profileMiniService:ProfileMiniService[DiscordWebhookModel],configService:ConfigService,redisService:RedisService):
        super().__init__(profileMiniService,None)
        WebhookAdapterInterface.__init__(self)

        self.depService = profileMiniService
        self.redisService = redisService
        self.configService = configService

    @property
    def model(self):
        return self.depService.model

    def build(self, build_state = ...):
        ...
    
    @WebhookAdapterInterface.retry
    def deliver(self,payload:DiscordBody|list[DiscordBody]):
        plain_cred = self.depService.credentials.to_plain()
        url = plain_cred['url']
        res = DiscordWebhook(
            url,
            username = self.model.username,
            avatar_url=self.model.avatar_url,
            wait= self.model.send_and_wait,
            timeout = self.model.timeout,
            thread_id = self.model.thread_id,
            thread_name = self.model.thread_name,
            allowed_mentions= self.model.allowed_mentions,
            rate_limit_retry=False,
            embeds=payload.get('embeds',None),
            attachments=payload.get('attachements',None),
            files=payload.get('files',None)
        ).execute()
        return res.status_code,res.content

    @WebhookAdapterInterface.batch
    @WebhookAdapterInterface.retry
    async def deliver_async(self,payload:DiscordBody|list[DiscordBody]):
        plain_cred = self.depService.credentials.to_plain()
        url = plain_cred['url']
        resp = await AsyncDiscordWebhook(
            url,
            username = self.model.username,
            avatar_url=self.model.avatar_url,
            wait= self.model.send_and_wait,
            timeout = self.model.timeout,
            thread_id = self.model.thread_id,
            thread_name = self.model.thread_name,
            allowed_mentions= self.model.allowed_mentions,
            rate_limit_retry=True,
            embeds=payload.get('embeds',None),
            attachments=payload.get('attachements',None),
            files=payload.get('files',None)
        ).execute()
        return resp.status_code,resp.content
    
@MiniService()
class ZapierWebhookMiniService(HTTPWebhookMiniService):

    def __init__(self,profileMiniService:ProfileMiniService[ZapierHTTPWebhookModel],configService:ConfigService,redisService:RedisService):
        self.depService = profileMiniService
        super().__init__(profileMiniService,configService,redisService)

@MiniService()      
class MakeWebhookMiniService(HTTPWebhookMiniService):
    """
    Make (Integromat) webhooks are HTTP endpoints that accept JSON or form data.
    This wrapper mirrors ZapierAdapter but provides the common header name
    X-Make-Signature if user wants HMAC verification.
    """
    def __init__(self,profileMiniService:ProfileMiniService[MakeHTTPWebhookModel],configService:ConfigService,redisService:RedisService):
        self.depService = profileMiniService
        super().__init__(profileMiniService,configService,redisService)

@MiniService()
class SlackIncomingWebhookMiniService(HTTPWebhookMiniService):
    """
    Slack Incoming Webhooks accept JSON payloads:
       {"text": "message", "blocks": [...], "attachments": [...]}

    Endpoint expectations:
      endpoint.url = Slack Webhook URL (provided by user)
      endpoint.secret = optional signing key (your HMAC, Slack does not require it)
      endpoint.config may include:
         - default_channel
         - default_username
         - default_icon
    """

    @property
    def model(self):
        return self.depService.model

    def __init__(self, profileMiniService:ProfileMiniService[SlackHTTPWebhookModel],configService:ConfigService,redisService:RedisService):
        super().__init__(profileMiniService,configService,redisService)
        self.depService = profileMiniService

    async def deliver_async(self,payload: Any):
        slack_message = self._convert_payload(payload)
        return await super().deliver_async(slack_message)
    
    def deliver(self,payload:Any):
        slack_message = self._convert_payload(payload)
        return super().deliver(slack_message)

    def _convert_payload(self, payload: Any) -> dict:
        """
        Maps your internal event payload into Slack-friendly JSON.
        Flexible: supports text, blocks, attachments, or raw Slack payload passthrough.
        """
        if isinstance(payload, dict):
            # If developer already sent Slack-native payload
            if "text" in payload or "blocks" in payload or "attachments" in payload:
                base = payload
            else:
                # fallback: embed your payload as text
                base = {"text": json.dumps(payload, ensure_ascii=False)}
        else:
            base = {"text": str(payload)}

        
        base["channel"] = self.model.channel
        base["username"] = self.model.username

        if self.model.icon_emoji:
            base["icon_emoji"] =  self.model.icon_emoji

        return base

@MiniService()
class N8NWebhookMiniService(HTTPWebhookMiniService):
    def __init__(self,profileMiniService:ProfileMiniService[MakeHTTPWebhookModel],configService:ConfigService,redisService:RedisService):
        super().__init__(profileMiniService,configService,redisService)
        self.depService = profileMiniService
