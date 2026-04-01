from typing import Dict, List, Literal, Optional, Self, Tuple
from aiohttp_retry import Union
from pydantic import BaseModel, Field, HttpUrl, field_serializer, field_validator, model_validator
from app.models.crawal4ai_model import MAX_URLS, DeepCrawlingStrategyModel, DigestConfigModel,KnowledgeGraphExtractionConfig, PDFLinkPreviewModel, SchemaExtractionConfig, SeedingURLModel, TextsExtractionConfig, URLGeneratorModel
from app.utils.constant import ParseStrategy
from .file_model import FileResponseUploadModel, UriMetadata
from app.classes.scheduler import TimedeltaSchedulerModel


###################################################################################################
###########################	          Base Ingest Model				 ##############################
###################################################################################################
class VectorConfig(BaseModel):
	collection_name: str
	category: str
	
class KGraphConfig(BaseModel):
	domain:str
	entities:Optional[list[str]] = []
	edges:Optional[list[str]] = []
	description:Optional[str] = None
	instruction:Optional[str] = None

class DataIngestModel(BaseModel):
	vector_config: Optional[VectorConfig] =  None
	graph_config: Optional[KGraphConfig] = None
	lang: Optional[str] = 'en'
	expires: Optional[TimedeltaSchedulerModel|None] = None
	defer_by: Optional[TimedeltaSchedulerModel|None] = None

	@field_validator('expires','defer_by')
	def transform_into_timedelta(cls,tDelta:TimedeltaSchedulerModel|None):
		if tDelta == None:
			return None
		delta = tDelta.build('timedelta')
		if delta.total_seconds() <= 10:
			return None
		return delta

	@field_serializer("defer_by","expires")
	def time_serialize(cls, v:TimedeltaSchedulerModel):
		return v.build('timedelta').total_seconds()

	@model_validator(mode='after')
	def config_validation(self:Self)->Self:
		if self.vector_config == None and self.graph_config == None:
			raise ValueError('You must define at least one ')

		return self


###################################################################################################
###########################		    File Ingest Model			     ##############################
###################################################################################################
class FileUploadDataIngestModel(DataIngestModel):
	strategy: ParseStrategy
	use_docling:bool = False

class IngestDataUriMetadata(UriMetadata):
	sha:str

class FileUploadIngestEnqueueResponse(FileResponseUploadModel):
    metadata: List[IngestDataUriMetadata] = []
	
class AbortedJobResponse(FileResponseUploadModel):
	aborted:bool
	status:str
	
###################################################################################################
###########################		           Web Crawling			     ##############################
###################################################################################################

class WebCrawlingDataIngestModel(DataIngestModel):
	extraction:Union[SchemaExtractionConfig | TextsExtractionConfig | KnowledgeGraphExtractionConfig]
	urls: List[HttpUrl] | SeedingURLModel | URLGeneratorModel
	pdf: Optional[PDFLinkPreviewModel] = None
	exclude_external_links:bool = True
	deep_crawling: Optional[DeepCrawlingStrategyModel] = None

	@field_validator("urls", mode="before")
	def parse_urls(cls, v):
		if isinstance(v,str):
			return [v]
		return v

	@field_validator("urls", mode="after")
	def parse_urls(cls, v):
		if isinstance(v,list):
			if len(v) > MAX_URLS *2:
				raise ValueError(f"You cannot provide more than {MAX_URLS *2} urls, you provided {len(v)}")
		return v
		
	@model_validator(mode='after')
	def invalidate_deep_crawling(self:Self)->Self:
		if isinstance(self.urls, URLGeneratorModel) and self.deep_crawling != None:
			raise ValueError('If the urls are generated you cannot use deep crawling as it will use too much ressource')

		return self

class IngestDataWebCrawlingResponse():
	...

###################################################################################################
###########################										     ##############################
###################################################################################################

class ResearchDataIngestModel(DataIngestModel):
	engine:Literal['google','bing','duckduckgo','google-scholar'] = 'google'
	max_pages: int = Field(default=10, gt=0, le=10)
	query:str
	config:DigestConfigModel


###################################################################################################
###########################										     ##############################
###################################################################################################


class EnqueueResponse(FileResponseUploadModel):
	...
