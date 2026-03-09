from pydantic import BaseModel
from app.models.file_model import FileResponseUploadModel

class DeleteDomainModel(FileResponseUploadModel):
    domain:str
    gateway_body:dict
    job_dequeued:list[str]
    jod_deleted:list[str]

class GraphitiSearchModel(BaseModel):
    ...