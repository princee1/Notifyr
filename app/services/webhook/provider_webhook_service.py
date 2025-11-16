import json
from typing import Any
from app.definition._service import BaseMiniService
from app.services.profile_service import ProfileMiniService
from app.services.webhook.http_webhook_service import HTTPWebhookMiniService
from app.models.webhook_model import DiscordHTTPWebhookModel, DiscordWebhookModel, MakeHTTPWebhookModel, SlackHTTPWebhookModel, ZapierHTTPWebhookModel
import json
from typing import Any

class DiscordHTTPWebhookMiniService(HTTPWebhookMiniService):
    """
    Discord incoming webhooks accept JSON payloads like {"content": "...", "embeds": [...]}.
    This adapter maps a generic payload to a Discord-friendly shape. It delegates actual
    HTTP delivery to HTTPAdapter.
    """
    def __init__(self,profileMiniService:ProfileMiniService[DiscordHTTPWebhookModel]):
        self.depService = profileMiniService
        super().__init__()

    async def deliver(self,payload: Any, event_type:str='event'):
        if isinstance(payload, dict):
            content = payload.get("message") or payload.get("text") or json.dumps(payload)
            embeds = payload.get("embeds")
        else:
            content = str(payload)
            embeds = None

        discord_payload = {"content": content}
        if embeds:
            discord_payload["embeds"] = embeds
        return await super().deliver(discord_payload,event_type)

# ---------- ZapierAdapter (thin HTTP wrapper, optional transforms) ----------
class ZapierAdapter(HTTPWebhookMiniService):
    
    def __init__(self,profileMiniService:ProfileMiniService[ZapierHTTPWebhookModel]):
        self.depService = profileMiniService
        super().__init__(profileMiniService)
        

    async def deliver(self,payload: Any,event_type:str):
        return await super().deliver(payload,event_type)

# ---------- MakeAdapter (Integromat) ----------
class MakeAdapter(HTTPWebhookMiniService):
    """
    Make (Integromat) webhooks are HTTP endpoints that accept JSON or form data.
    This wrapper mirrors ZapierAdapter but provides the common header name
    X-Make-Signature if user wants HMAC verification.
    """
    def __init__(self,profileMiniService:ProfileMiniService[MakeHTTPWebhookModel]):
        self.depService = profileMiniService
        super().__init__(profileMiniService)

    async def deliver(self, payload: Any,event_type):
        return await super().deliver(payload, event_type)

class SlackAdapterIcoming(HTTPWebhookMiniService):
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

    def __init__(self, profileMiniService:ProfileMiniService[SlackHTTPWebhookModel]):
        self.profileMiniService = profileMiniService
        super().__init__(profileMiniService)

    async def deliver(self,payload: Any):

        slack_message = self._convert_payload(payload)
        return await super().deliver(slack_message)

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
