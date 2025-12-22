import json
from typing import Any, Dict, Optional, TypedDict
from aiohttp_retry import Tuple
from app.definition._service import BaseMiniService, MiniService
from app.interface.webhook_adapter import WebhookAdapterInterface
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from app.services.profile_service import ProfileMiniService
from app.services.webhook.http_webhook_service import HTTPWebhookMiniService
from app.models.webhook_model import DiscordWebhookModel, MakeHTTPWebhookModel, SlackHTTPWebhookModel, ZapierHTTPWebhookModel
from discord_webhook import DiscordEmbed,DiscordWebhook,AsyncDiscordWebhook

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
        return await super().deliver_deliver(slack_message)
    
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
