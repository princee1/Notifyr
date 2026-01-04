from typing import Optional
from pydantic import BaseModel, field_validator
from .file_model import FileResponseUploadModel
from app.classes.scheduler import TimedeltaSchedulerModel


class DataIngestTask(BaseModel):
	collection_name: str
	lang: Optional[str] = 'en'
	content_type: Optional[str] = None
	expires: Optional[TimedeltaSchedulerModel] = None
	defer_by: Optional[TimedeltaSchedulerModel] = None

	@field_validator('expires','defer_by')
	def transform_into_timedelta(tDelta:TimedeltaSchedulerModel|None):
		if tDelta == None:
			return None
		return tDelta.build('timedelta')

class DataEnqueueResponse(FileResponseUploadModel):
	pass

class AbortedJobResponse(FileResponseUploadModel):
	aborted:bool
	state:str

	
class EnqueueResponse(BaseModel):
	...

