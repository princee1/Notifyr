from enum import Enum
from typing import Optional
from pydantic import BaseModel, PrivateAttr, field_validator

from app.utils.constant import ParseStrategy
from .file_model import FileResponseUploadModel
from app.classes.scheduler import TimedeltaSchedulerModel

class DataIngestTask(BaseModel):
	collection_name: str
	lang: Optional[str] = 'en'
	content_type: Optional[str] = None
	expires: Optional[TimedeltaSchedulerModel] = None
	defer_by: Optional[TimedeltaSchedulerModel] = None
	_request_id:str = PrivateAttr(None)

	def model_dump(self, *, mode = 'python', include = None, exclude = None, context = None, by_alias = None, exclude_unset = False, exclude_defaults = False, exclude_none = False, exclude_computed_fields = False, round_trip = False, warnings = True, fallback = None, serialize_as_any = False):
		temp =  super().model_dump(mode=mode, include=include, exclude=exclude, context=context, by_alias=by_alias, exclude_unset=exclude_unset, exclude_defaults=exclude_defaults, exclude_none=exclude_none, exclude_computed_fields=exclude_computed_fields, round_trip=round_trip, warnings=warnings, fallback=fallback, serialize_as_any=serialize_as_any)
		return {
			'request_id':self._request_id,
			**temp
		}

	@field_validator('expires','defer_by')
	def transform_into_timedelta(tDelta:TimedeltaSchedulerModel|None):
		if tDelta == None:
			return None
		return tDelta.build('timedelta')
	
class FileDataIngestTask(DataIngestTask):
	strategy: ParseStrategy
	use_docling:bool = False

class FileDataEnqueueResponse(FileResponseUploadModel):
	pass

class AbortedJobResponse(FileResponseUploadModel):
	aborted:bool
	state:str

	
class EnqueueResponse(BaseModel):
	...

