from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TypedDict
from pydantic import BaseModel
from app.classes.chunk import Chunk
from app.definition._error import BaseError
from app.models.llm_model import CrawlLLMConfigModel, WebResearchConfigModel


@dataclass
class CrawlLLMConfig:
	provider_id:str
	provider: str
	model: CrawlLLMConfigModel | WebResearchConfigModel
	api_token: str

	def formatted_provider(self) -> str:
		return f"{self.provider}/{self.model.model}"

	@property
	def _model(self)->str:
		return self.model.model

class CrawlTokenUsage(TypedDict):
    """Token usage report for cost tracking."""
    input_tokens: int
    output_tokens: int
    step: Optional[str] = None

class CrawlTokenUsageReport(TypedDict):
    model:str
    provider:str
    provider_id:str
    tokens:List[CrawlTokenUsage]

###################################################################################################
###########################		  Error Definitions					     ##############################
###################################################################################################

class CrawlNotSucceededError(BaseError):
	def __init__(self, url: str):
		super().__init__(url)
		self.url = url

class Crawl4AIModeConfigMissingError(BaseError):
	def __init__(self, config: str):
		super().__init__(config)
		self.config = config

class SchemaGenerationError(BaseError):
	def __init__(self, schema_name: str, reason: str):
		super().__init__(f"Schema '{schema_name}': {reason}")
		self.schema_name = schema_name

class UrlDescriptionNotFoundError(BaseError):
    def __init__(self, url:str,reason):
        super().__init__()
        self.url = url
        self.reason = reason

class NoURLToCrawlError(BaseError):
    ...

class SchemaHTMLExampleNotFoundError(BaseError):
    def __init__(self,schema_name,schema_url,reason):
        super().__init__()
        self.schema_name =schema_name
        self.schema_url = schema_url
        self.reason = reason
class SchemaHasNoContentError(BaseError):
    def __init__(self,schema_name,schema_url,reason):
        super().__init__()
        self.schema_name =schema_name
        self.schema_url = schema_url
        self.reason = reason

class SchemaFetchError(BaseError):
    def __init__(self,schema_name,schema_url,reason):
        super().__init__()
        self.schema_name =schema_name
        self.schema_url = schema_url
        self.reason = reason

class NoInputHtmlSchemaError(BaseError):
    def __init__(self, schema_name,schema_urls):
        super().__init__()
        self.schema_name = schema_name
        self.schema_urls = schema_urls

class SchemaCouldNotBeGeneratedError(BaseError):
    def __init__(self, schema_name,schema_url,strategy):
        super().__init__()
        self.schema_name = schema_name
        self.schema_url = schema_url
        self.strategy = strategy

class BadSchemaGenerationStrategyError(BaseError):
    def __init__(self, strategy):
        super().__init__()
        self.strategy = strategy

class CrawlError(TypedDict):
    name:str
    url: str
    message: str
	
###################################################################################################
###########################		  Type Definitions					     ##############################
###################################################################################################

class CrawlText(BaseModel):
    text:str
    title:str
    id:str
    topics:List[str]
    keywords:List[str]
    section: str
    content_type: str

class CrawlTextModel(BaseModel):
	texts:List[CrawlText]


@dataclass
class CrawlResultMetadata:
    url: str
    title: Optional[str] = None
    source: Optional[str] = None
    description: Optional[str] = None
    success: bool = False
    result: Optional[dict] = None
    error: Optional[str] = None
    extracted_content: list[Any] = None
    markdown_content: Optional[str] = None
    chunks: List[Chunk] = field(default_factory=list)

class CrawlDocumentSize(TypedDict):
    size:int
    url:str
    description:str

class CrawlState(TypedDict):
    deep_crawl:Dict
    cancelled:bool



class DigestURLState(TypedDict):
    ...

DigestState  = Dict[str, DigestURLState]