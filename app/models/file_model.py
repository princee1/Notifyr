from typing import Dict, List, Optional
from pydantic import BaseModel


class UriMetadata(BaseModel):
    uri: str
    size: float

class UploadError(BaseModel):
    path: Optional[str] = None
    reason: str
    fix:str

class FileResponseUploadModel(BaseModel):
    metadata: List[UriMetadata] = []
    errors: Dict[str,UploadError] = {}

