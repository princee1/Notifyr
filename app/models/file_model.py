from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class UriMetadata(BaseModel):
    uri: str
    size: float

class UploadError(BaseModel):
    path: Optional[str] = None
    fix:Optional[str] = None
    reason: str

class FileResponseUploadModel(BaseModel):
    metadata: List[UriMetadata] = Field(default_factory=list)
    errors: Dict[str,UploadError] = Field(default_factory=dict)

