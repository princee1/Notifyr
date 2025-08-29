from typing import Self
from pydantic import BaseModel

class GlobalVarModel(BaseModel):
    model_config = {
        "extra": "allow"
    }
    

class SettingsModel(BaseModel):
    AUTH_EXPIRATION: int
    REFRESH_EXPIRATION: int
    CHAT_EXPIRATION: int
    ASSET_LANG: str

    
    def copy(self) -> Self:
        return SettingsModel(**self.model_dump())
    
    