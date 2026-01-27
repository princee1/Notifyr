from enum import Enum
from typing import List, Literal, Optional
from pydantic import BaseModel, field_serializer, field_validator

from app.utils.constant import ParseStrategy
from .file_model import FileResponseUploadModel, UploadError, UriMetadata
from app.classes.scheduler import TimedeltaSchedulerModel


class ProviderModel(BaseModel):
	provider:str
	model:str


class DataIngestModel(BaseModel):
	collection_name: str
	lang: Optional[str] = 'en'
	category: Optional[str] = None
	provider:str
	knowledge:Literal['vector','k-graph','both']= 'vector'
	expires: Optional[TimedeltaSchedulerModel|None] = None
	defer_by: Optional[TimedeltaSchedulerModel|None] = None

	@field_validator('expires','defer_by')
	def transform_into_timedelta(tDelta:TimedeltaSchedulerModel|None):
		if tDelta == None:
			return None
		delta = tDelta.build('timedelta')
		if delta.total_seconds() <= 10:
			return None
		return delta

	@field_serializer("defer_by","expires")
	def time_serialize(self, v:TimedeltaSchedulerModel):
		return v.build('timedelta').total_seconds()
	
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

	
class EnqueueResponse(FileResponseUploadModel):
	...
