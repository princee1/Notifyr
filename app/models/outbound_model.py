from .webhook_model import *

class HTTPOutboundModel(BaseProfileModel):
    signature_config: Optional[SignatureConfig]=None
    method: Literal["POST", "PUT", "PATCH", "DELETE", "GET"] = "POST"
    encoding:BodyEncoding = 'json'
    headers: Optional[Dict[str, str]] = Field(default_factory=dict)
    require_tls: bool = True
    secret_headers : Optional[Dict[str, str]] = Field(default_factory=dict)
    params: Optional[Dict[str, str]] = Field(default_factory=dict)
    url: str = Field(max_length=500)
    auth:Optional[AuthConfig] = None

    _secret_key:ClassVar[list[str]] = ['auth','secret_headers','signature_config','url']

    @field_validator('url',mode='after')
    def url_validator(cls,url):
        HttpUrl(url)
        return url

    @model_validator(mode='after')
    def validate_security(self,)->Self:
        if self.signature_config:
            if not self.signature_config["secret"]:
                self.signature_config["secret"] = generateId(25)

            if not self.signature_config["algo"]:
                self.signature_config['algo'] = 'sha256'
            
            if not self.signature_config["header_name"]:
                self.signature_config["header_name"] = 'X-Signature'

        if self.auth:
            if not self.auth['password']:
                raise ValueError('Auth password is required')
            
            if not self.auth['username']:
                raise ValueError('Auth username is required')

        return self

OUTBOUND_PREFIX = 'outbound'

ProfilModelValues.update(
    {
        f'{OUTBOUND_PREFIX}/http':HTTPOutboundModel
    }
)