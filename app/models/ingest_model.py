from typing import List, Optional, Self
from pydantic import BaseModel, field_serializer, field_validator, model_validator
from app.utils.constant import ParseStrategy
from .file_model import FileResponseUploadModel, UriMetadata
from app.classes.scheduler import TimedeltaSchedulerModel


class VectorConfig(BaseModel):
	collection_name: str
	category: str
	
class KGraphConfig(BaseModel):
	domain:str
	entities:Optional[list[str]] = []
	edges:Optional[list[str]] = []
	description:Optional[str] = None
	instruction:Optional[str] = None


###################################################################################################
###########################										     ##############################
###################################################################################################

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

class DataIngestFileModel(DataIngestModel):
	strategy: ParseStrategy
	use_docling:bool = False

class DigestStrategy(BaseModel):
	query:str

class DataIngestWebCrawlingModel(DataIngestModel):
	extraction_type:str
	schemas:Optional[List[str]] = None
	instruction:Optional[str] = None	
	digest_strategy: ...
	url:str

###################################################################################################
###########################										     ##############################
###################################################################################################

class IngestDataUriMetadata(UriMetadata):
	sha:str

class IngestFileEnqueueResponse(FileResponseUploadModel):
    metadata: List[IngestDataUriMetadata] = []
	
class AbortedJobResponse(FileResponseUploadModel):
	aborted:bool
	status:str
	
class EnqueueResponse(FileResponseUploadModel):
	...
