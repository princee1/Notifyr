from pydantic import BaseModel, Field
from app.models.ingest_model import DeleteIngestDataModel

class DeleteDomainModel(DeleteIngestDataModel):
    domain:str
    
class GraphitiSearchModel(BaseModel):
    ...