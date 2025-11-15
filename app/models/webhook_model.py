from typing import ClassVar, Dict, List, Literal, Optional
from app.classes.profiles import BaseProfileModel
from app.utils.constant import MongooseDBConstant
from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from typing_extensions import TypedDict

######################################################
# Communication-related Profiles (Root)
######################################################

class BatchConfig(TypedDict):
    allow:bool = False
    max_batch:int = 50
    flush_interval:float = 5.0

class SignatureConfig(TypedDict):
    allow:bool = True
    secret:Optional[SecretStr]= None
    algo:Optional[Literal['sha256']] = None
    header_name:Optional[str] = None

BodyEncoding = Literal['raw','json','form']

class WebhookProfileModel(BaseProfileModel):
    retry_statuses: List[int] = Field(default_factory=lambda: [408, 429, 500, 502, 503, 504])
    batch_config: Optional[BatchConfig] = None
    timeout: float = 10.0
    max_connections: int = 100
    max_attempt:int = 3
    send_and_wait:bool = True
    url: str
    
    @field_validator("timeout")
    def timeout_positive(cls, v):
        if v <= 0:
            raise ValueError("timeout_seconds must be > 0")
        return v

    _collection:ClassVar[Optional[str]]= MongooseDBConstant.WEBHOOK_PROFILE_COLLECTION
    class Settings:
        is_root=True
        collection=MongooseDBConstant.WEBHOOK_PROFILE_COLLECTION



class HTTPWebhookModel(WebhookProfileModel):
    url: AnyHttpUrl
    signature_config: SignatureConfig
    method: Literal["POST", "PUT", "PATCH", "DELETE", "GET"] = "POST"
    encoding:BodyEncoding = 'json'
    headers: Optional[Dict[str, str]] = Field(default_factory=dict)
    require_tls: bool = True
    http2:bool = False
    secret_headers : Optional[Dict[str, str]] = Field(default_factory=dict)
    params: Optional[Dict[str, str]] = Field(default_factory=dict)


class DiscordWebhookModel(HTTPWebhookModel):
    username: Optional[str] = None
    avatar_url: Optional[AnyHttpUrl] = None
    mention_everyone: bool = False
    webhook_token:SecretStr
    webhook_id:str
    
class KafkaWebhookModel(WebhookProfileModel):
    client_id:str
    bootstrap_servers: List[str]  # ["kafka1:9092", "kafka2:9092"]
    topic: str
    key:Optional[str] = None
    key_template: Optional[str] = None  # templating string to build message key from payload or delivery_id
    acks: Literal["all", "1", "0"] = "all"
    partition: Optional[int] = None
    compression: Optional[Literal["gzip", "snappy", "lz4", "zstd"]] = None
    enable_idempotence:bool=False

    @field_validator("bootstrap_servers")
    def non_empty_bootstrap(cls, v):
        if not v:
            raise ValueError("bootstrap_servers must include at least one server")
        return v

class SQSWebhookModel(WebhookProfileModel):
    region: Optional[str] = None
    aws_access_key_id: str
    aws_secret_access_key: SecretStr
    message_group_id_template: Optional[str] = None 
    deduplication_id_template: Optional[str] = None
    queue_url:str
    

class RedisWebhookModel(WebhookProfileModel):
    url:str
    stream_key: str = "notifyr"
    mode: Literal["stream", "list", "pubsub"] = "stream"
    stream_maxlen: Optional[int] = None
    db:int = Field(0,ge=0,le=15)  
    port: int = 6379
    from_url:bool=False
    username:Optional[str]=None
    password:Optional[SecretStr] = None
    # TODO add url to the secret