from typing import Self, TypedDict,Optional,Dict,List,Literal,ClassVar
from pydantic import Field, HttpUrl,field_validator,model_validator
from app.classes.profiles import BaseProfileModel, ProfilModelValues

Method = Literal["POST", "PUT", "PATCH", "DELETE", "GET"] 

class AuthConfig(TypedDict):
    username:str
    password:str

class OutboundCredentials(TypedDict):
    auth:AuthConfig
    secret_headers:dict
    secret_params:dict
    url:Optional[str]

class HTTPOutboundModel(BaseProfileModel):
    method: List[Method] = Field(default_factory=list)
    url: str = Field(max_length=500)
    require_tls: bool = True
    headers: Optional[Dict[str, str]] = Field(default_factory=dict)
    secret_headers : Optional[Dict[str, str]] = Field(default_factory=dict)
    params: Optional[Dict[str, str]] = Field(default_factory=dict)
    secret_params: Optional[Dict[str, str]] = Field(default_factory=dict)
    auth:Optional[AuthConfig] = None

    _secret_key:ClassVar[list[str]] = ['auth','secret_headers','url','secret_params']

    @field_validator('url',mode='after')
    def url_validator(cls,url):
        HttpUrl(url)
        return url

    @field_validator('method',mode='after')
    def method_validator(cls,m):
        return list(set(m))

    @model_validator(mode='after')
    def validate_auth(self,)->Self:
        if self.auth:
            if not self.auth.get('password',None):
                raise ValueError('Auth password is required')
            
            if not self.auth.get('password'):
                raise ValueError('Auth username is required')

        return self

OUTBOUND_PREFIX = 'outbound'

ProfilModelValues.update(
    {
        f'{OUTBOUND_PREFIX}/http':HTTPOutboundModel
    }
)