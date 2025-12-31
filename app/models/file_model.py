from typing import Tuple
from pydantic import BaseModel


class FileResponseUploadModel(BaseModel):
    meta:Tuple[str,float]
