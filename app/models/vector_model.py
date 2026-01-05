from aiohttp_retry import Any
from openai import BaseModel
from app.models.file_model import FileResponseUploadModel

class DeleteCollectionModel(FileResponseUploadModel):
    gateway_body:dict


class QdrantCollectionModel(BaseModel):
    collection_name:str
    metadata:dict[str,Any]