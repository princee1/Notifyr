import math
from typing import Dict, List, Literal, Optional, Self, Tuple
from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator
from app.models.crawal4ai_model import DeepCrawlingStrategyModel, DigestConfigModel, ExtractionStrategyModel, SeedingURLModel, URLGeneratorModel
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


class DataIngestFileModel(DataIngestModel):
	strategy: ParseStrategy
	use_docling:bool = False

class IngestDataUriMetadata(UriMetadata):
	sha:str

class IngestFileEnqueueResponse(FileResponseUploadModel):
    metadata: List[IngestDataUriMetadata] = []
	
class AbortedJobResponse(FileResponseUploadModel):
	aborted:bool
	status:str
	
###################################################################################################
###########################										     ##############################
###################################################################################################

class DigestStrategyModel(BaseModel):
	start_url:str
	query:List[str]
	config:DigestConfigModel

class DataIngestWebCrawlingModel(DataIngestModel):
	deep_crawling: Optional[DeepCrawlingStrategyModel] = None
	extraction:Optional[ExtractionStrategyModel] = None
	urls: List[str] | SeedingURLModel | URLGeneratorModel

	@field_validator("urls", mode="before")
	def parse_urls(cls, v):
		if isinstance(v,str):
			return [v]
		return v
	
class IngestDataWebCrawlingResponse:
	...

###################################################################################################
###########################										     ##############################
###################################################################################################


class EnqueueResponse(FileResponseUploadModel):
	...
