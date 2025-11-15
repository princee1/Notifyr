# ---------- DiscordAdapter (thin wrapper, maps payload -> Discord webhook)
from app.services.webhook.http_webhook_service import HTTPWebhookMiniService
from app.models.webhook_model import DiscordWebhookModel


class DiscordHTTPWebhookMiniService(HTTPWebhookMiniService):
    """
    Discord incoming webhooks accept JSON payloads like {"content": "...", "embeds": [...]}.
    This adapter maps a generic payload to a Discord-friendly shape. It delegates actual
    HTTP delivery to HTTPAdapter.
    """
    def __init__(self):
        super().__init__()



    async def deliver(self,payload: Any, event_type:str='event'):
        # Map payload: choose content, use embed if present
        if isinstance(payload, dict):
            content = payload.get("message") or payload.get("text") or json.dumps(payload)
            embeds = payload.get("embeds")
        else:
            content = str(payload)
            embeds = None

        discord_payload = {"content": content}
        if embeds:
            discord_payload["embeds"] = embeds

        # Discord webhooks may reject HMAC headers, but we keep support if secret is set.
        return await super().deliver(discord_payload,event_type)

# ---------- ZapierAdapter (thin HTTP wrapper, optional transforms) ----------
class ZapierAdapter(HTTPWebhookMiniService):
    """
    Zapier typically accepts JSON or form-encoded webhooks. This wrapper uses HTTPAdapter
    but provides convenience mapping and optional "zapier-style" fields:
      - If endpoint.config.use_form=true -> send form-encoded with top-level payload fields.
      - Allows an optional 'zapier_signature_header' name if you want to sign.
    Zapier doesn't mandate a signature header by default; many users simply paste the Zap URL.
    """
    def __init__(self, http_adapter: Optional[HTTPAdapter] = None):
        self.http = http_adapter or HTTPAdapter()

    async def deliver(self, endpoint: EndpointConfig, payload: Any, delivery_id: str, attempt: int):
        cfg = endpoint.config or {}
        # Zapier often expects JSON — but some users choose form.
        if cfg.get("use_form"):
            # transform payload to flat dict for form post if it's a dict
            form_payload = payload if isinstance(payload, dict) else {"payload": json.dumps(payload)}
            # mark encoding override
            endpoint.config = {**endpoint.config, "encoding": "form"}
            return await self.http.deliver(endpoint, form_payload, delivery_id, attempt)

        # Optional signature header name for Zapier (if user requests extra security)
        if endpoint.secret:
            # default header name for Zapier is X-Zapier-Signature (not an official standard)
            sig_header = cfg.get("signature_header", "X-Zapier-Signature")
            # set signing config for HTTP adapter to use that header name
            endpoint.config = {**endpoint.config, "signing": {"header": sig_header, "algo": "sha256"}}
        return await self.http.deliver(endpoint, payload, delivery_id, attempt)


# ---------- MakeAdapter (Integromat) ----------
class MakeAdapter(HTTPWebhookMiniService):
    """
    Make (Integromat) webhooks are HTTP endpoints that accept JSON or form data.
    This wrapper mirrors ZapierAdapter but provides the common header name
    X-Make-Signature if user wants HMAC verification.
    """
    def __init__(self, http_adapter: Optional[HTTPAdapter] = None):
        self.http = http_adapter or HTTPAdapter()

    async def deliver(self, endpoint: EndpointConfig, payload: Any, delivery_id: str, attempt: int):
        cfg = endpoint.config or {}
        if cfg.get("use_form"):
            endpoint.config = {**endpoint.config, "encoding": "form"}
        if endpoint.secret:
            sig_header = cfg.get("signature_header", "X-Make-Signature")
            endpoint.config = {**endpoint.config, "signing": {"header": sig_header, "algo": "sha256"}}
        return await self.http.deliver(endpoint, payload, delivery_id, attempt)
    


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
    def __init__(self, http_adapter: HTTPAdapter = None):
        self.http = http_adapter or HTTPAdapter()

    async def deliver(
        self,
        endpoint: EndpointConfig,
        payload: Any,
        delivery_id: str,
        attempt: int
    ) -> Tuple[int, bytes]:

        # Map your internal payload → Slack message structure
        slack_message = self._convert_payload(payload, endpoint)

        # Slack webhooks require POST JSON
        return await self.http.deliver(endpoint, slack_message, delivery_id, attempt)

    def _convert_payload(self, payload: Any, endpoint: EndpointConfig) -> dict:
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

        # Add defaults if user configured them
        cfg = endpoint.config or {}
        if cfg.get("default_channel"):
            base["channel"] = cfg["default_channel"]

        if cfg.get("default_username"):
            base["username"] = cfg["default_username"]

        if cfg.get("default_icon"):
            # can be emoji like :robot:
            base["icon_emoji"] = cfg["default_icon"]

        return base
