from typing import List, Tuple
from pydantic import BaseModel


class FileResponseUploadModel(BaseModel):
    meta:List[Tuple[str,float]]

