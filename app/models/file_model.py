from typing import Dict, List, Optional
from pydantic import BaseModel


class UriMetadata(BaseModel):
    uri: str
    size: float

class UploadError(BaseModel):
    path: Optional[str] = None
    fix:Optional[str] = None
    reason: str

class FileResponseUploadModel(BaseModel):
    metadata: List[UriMetadata] = []
    errors: Dict[str,UploadError] = {}

