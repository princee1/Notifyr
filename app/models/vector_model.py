from typing import Any, Dict, List
from pydantic import BaseModel, Field
from app.models.ingest_model import DeleteIngestDocumentModel

class DeleteCollectionModel(DeleteIngestDocumentModel):
    collection_name:str

class QdrantCollectionModel(BaseModel):
    collection_name:str
    metadata:dict[str,Any]