from typing import Self
from pydantic import BaseModel

class GlobalVarModel(BaseModel):
    model_config = {
        "extra": "allow"
    }
    