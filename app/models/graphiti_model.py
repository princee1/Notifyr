from pydantic import BaseModel, Field
from app.models.ingest_model import DeleteIngestDocumentModel

class DeleteDomainModel(DeleteIngestDocumentModel):
    domain:str
    
class GraphitiSearchModel(BaseModel):
    ...