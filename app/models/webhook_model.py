from typing import ClassVar, Dict, List, Literal, Optional, Self
from typing_extensions import TypedDict
from urllib.parse import quote_plus
from app.classes.profiles import BaseProfileModel,ProfilModelValues
from app.utils.constant import MongooseDBConstant, VaultConstant
from pydantic import AnyHttpUrl, BaseModel, Field, HttpUrl, SecretStr, field_validator,model_validator, root_validator
from app.utils.helper import generateId

######################################################
# Communication-related Profiles (Root)
######################################################

class BatchConfig(TypedDict):
    max_batch:int
    flush_interval:float
    mode:Literal['single','group']

class AuthConfig(TypedDict):
    username:str
    password:str

class SignatureConfig(TypedDict):
    secret:Optional[str]= None
    algo:Optional[Literal['sha256']] = None
    header_name:Optional[str] = None

BodyEncoding = Literal['raw','json','form']

class WebhookProfileModel(BaseProfileModel):
    _retry_statuses: ClassVar[List[int]] = [408, 429, 500, 502, 503, 504]
    batch_config: Optional[BatchConfig] = None
    timeout: float = Field(3,ge=1,le=25)
    max_attempt:int = Field(3,ge=1,le=20)
    send_and_wait:bool = True
    url: str = Field(max_length=500)
    
    @field_validator('batch_config',mode='after')
    def validate_batch_config(cls,batch_config:BatchConfig):
        if batch_config:
            if not ( 20 < batch_config["max_batch"] <1500):
                raise ValueError('Max batch size must be between 20 and 1500')
            if not (5.0 < batch_config['flush_interval'] <260):
                raise ValueError('Flush interval must be between 5.0 and 260 seconds')
            mode = batch_config.get("mode",None)
            if not mode:
                raise ValueError('Batch mode is required')
            if mode not in ['single','group']:
                raise ValueError('Batch mode must be either single or group')
            batch_config['mode']='single' # TODO default to single for now

        return batch_config

    _collection:ClassVar[Optional[str]]= MongooseDBConstant.WEBHOOK_PROFILE_COLLECTION
    _vault:ClassVar[Optional[str]] = VaultConstant.WEBHOOK_SECRETS

    class Settings:
        is_root=True
        name=MongooseDBConstant.WEBHOOK_PROFILE_COLLECTION


################################################################################################
            #######################    HTTPWebhook     #######################
################################################################################################

class HTTPWebhookModel(WebhookProfileModel):
    signature_config: Optional[SignatureConfig]=None
    method: Literal["POST", "PUT", "PATCH", "DELETE", "GET"] = "POST"
    encoding:BodyEncoding = 'json'
    headers: Optional[Dict[str, str]] = Field(default_factory=dict)
    require_tls: bool = True
    secret_headers : Optional[Dict[str, str]] = Field(default_factory=dict)
    params: Optional[Dict[str, str]] = Field(default_factory=dict)
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

class DiscordWebhookModel(HTTPWebhookModel):
    username: Optional[str] = None
    avatar_url: Optional[AnyHttpUrl] = None
    thread_id:Optional[str] =None
    thread_name:Optional[str] =None
    allowed_mentions:Optional[Dict[str, List[str]]] = None

class SlackHTTPWebhookModel(HTTPWebhookModel):
    channel:str = Field(max_length=50)
    username:str = Field(max_length=100)
    icon_emoji:Optional[str] = Field(None,max_length=20)

class ZapierHTTPWebhookModel(HTTPWebhookModel):
    encoding:Literal['json','form']='json'

class MakeHTTPWebhookModel(HTTPWebhookModel):
    encoding:Literal['json','form'] = 'json'

    # pipe the model name

class N8nHTTPWebhookModel(HTTPWebhookModel):
    ...    


################################################################################################
            #######################     Broker   ###########################
################################################################################################

class KafkaWebhookModel(WebhookProfileModel):
    client_id:str = Field(max_length=200)
    bootstrap_servers: List[str]  # ["kafka1:9092", "kafka2:9092"]
    topic: str = Field(max_length=100)
    key:Optional[str] = Field(None,max_length=50)
    key_template: Optional[str] = None  # templating string to build message key from payload or delivery_id
    acks: Literal["all", "1", "0"] = "all"
    partition: Optional[int] = None
    compression: Optional[Literal["gzip", "snappy", "lz4", "zstd"]] = None
    enable_idempotence:bool=False

    auth:Optional[AuthConfig] = None

    _secret_key:ClassVar[list[str]] = ['auth']

    @field_validator("bootstrap_servers")
    def non_empty_bootstrap(cls, v):
        if not v:
            raise ValueError("bootstrap_servers must include at least one server")
        return v

class SQSWebhookModel(WebhookProfileModel):
    region: str = Field(max_length=50)
    aws_access_key_id: str = Field(max_length=100)
    aws_secret_access_key: str = Field(max_length=100)
    message_group_id_template: Optional[str] = None 
    deduplication_id_template: Optional[str] = None
    # NOTE queue_url is the url
    
    _secret_key:ClassVar[list[str]] = ['aws_secret_access_key']

class RedisWebhookModel(WebhookProfileModel):
    url:str = Field(max_length=500)
    stream_key: str = Field("notifyr",max_length=100)
    mode: Literal["stream", "list", "pubsub"] = "stream"
    stream_maxlen: Optional[int] = None
    db:int = Field(0,ge=0,le=15)  
    port: int = 6379
    from_url:bool=False
    auth: Optional[AuthConfig] = None
    
    _secret_key:ClassVar[list[str]] = ['url','auth']


################################################################################################
            #######################    Database   ###########################
################################################################################################
class DBWebhookModel(WebhookProfileModel):
    auth: Optional[AuthConfig] = None
    from_url: bool = True     
    url: Optional[str] = None               
    host: Optional[str] = None
    port: Optional[int] = None
    database:Optional[str] = None

    _secret_key: ClassVar[list[str]] = ["url", "auth"]
    _scheme:ClassVar[Optional[str]] = None

    class Settings:
        abstract=True
        name=MongooseDBConstant.WEBHOOK_PROFILE_COLLECTION

    @model_validator(mode='after')
    def validate_connection(self)->Self:

        if self.from_url:
            url = HttpUrl(self.url)
            if not self.url:
                raise ValueError("`url` is required when `from_url=True`.")
            
            if url.scheme != self._scheme:
                raise ValueError(f'Scheme does not match {self._scheme}')
            
            self.database= url.path

        else:
            if not self.host:
                raise ValueError("`host` is required when `from_url=False`.")
            if not self.port:
                raise ValueError("`port` is required when `from_url=False`.")
            if not self.database:
                raise ValueError("`database` is required when `from_url=False`.")

        return self

class PostgresWebhookModel(DBWebhookModel):
    url: Optional[str] = None
    port: Optional[int] = 5432
    table:str = Field("notifyr_webhooks",max_length=150)
    _scheme:ClassVar[Optional[str]] = 'postgresql'

class MongoDBWebhookModel(DBWebhookModel):
    url: Optional[str] = None
    port: Optional[int] = 27017
    collection:str = Field("notifyr_webhooks",max_length=150)
    _scheme:ClassVar[Optional[str]] = 'mongodb'

######################################################
# Registry of Profile Implementations
######################################################

class WebhookModelConstant:
    DISCORD='discord'
    SLACK='slack'
    ZAPIER='zapier'
    MAKE='make'
    N8N='n8n'
    KAFKA='kafka'
    SQS='sqs'
    REDIS='redis'
    POSTGRES='postgres'
    MONGODB='mongodb'
    HTTP='http'

ProfilModelValues.update({
    WebhookModelConstant.DISCORD:DiscordWebhookModel,
    WebhookModelConstant.SLACK:SlackHTTPWebhookModel,
    WebhookModelConstant.ZAPIER:ZapierHTTPWebhookModel,
    WebhookModelConstant.MAKE:MakeHTTPWebhookModel,
    WebhookModelConstant.N8N:N8nHTTPWebhookModel,
    WebhookModelConstant.KAFKA:KafkaWebhookModel,
    WebhookModelConstant.SQS:SQSWebhookModel,
    WebhookModelConstant.REDIS:RedisWebhookModel,
    WebhookModelConstant.POSTGRES:PostgresWebhookModel,
    WebhookModelConstant.MONGODB:MongoDBWebhookModel,
    WebhookModelConstant.HTTP:HTTPWebhookModel,
})