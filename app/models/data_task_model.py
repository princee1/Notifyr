from typing import Any, Optional
from pydantic import PrivateAttr,BaseModel
from .file_model import FileResponseUploadModel


class FileIngestTask(BaseModel):
	"""Model used to enqueue a file ingestion task.

	The `path` may be a temporary path where the uploaded file was saved, an object key,
	or a URL accessible to the worker.
	"""	
	collection_name: str
	lang: Optional[str] = 'en'
	content_type: Optional[str] = None
	_file_path:str = PrivateAttr(None)
	_job_id:str = PrivateAttr(None)
	_size:int = PrivateAttr(None)
	
	def model_dump(self, *, mode = 'python', include = None, exclude = None, context = None, by_alias = None, exclude_unset = False, exclude_defaults = False, exclude_none = False, exclude_computed_fields = False, round_trip = False, warnings = True, fallback = None, serialize_as_any = False):
		temp = super().model_dump(mode=mode, include=include, exclude=exclude, context=context, by_alias=by_alias, exclude_unset=exclude_unset, exclude_defaults=exclude_defaults, exclude_none=exclude_none, exclude_computed_fields=exclude_computed_fields, round_trip=round_trip, warnings=warnings, fallback=fallback, serialize_as_any=serialize_as_any)
		return {'file_path': self._file_path,"job_id":self._job_id,"size":self._size,  **temp}
	
	def set_meta(self,file_path,jod_id,size):
		self._file_path = file_path
		self._job_id = jod_id
		self._size = size

class EnqueueResponse(FileResponseUploadModel):
	jobs_ids:list[str] = []
	errors: dict[str:Any] ={}

	

