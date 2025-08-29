from typing import Self
from pydantic import BaseModel, model_validator

from app.classes.template import AVAILABLE_LANG

SECONDS_IN_A_HOUR = 3600

class GlobalVarModel(BaseModel):
    model_config = {
        "extra": "allow"
    }
    

class SettingsModel(BaseModel):
    AUTH_EXPIRATION: int = None
    REFRESH_EXPIRATION: int = None
    CHAT_EXPIRATION: int = None
    ASSET_LANG: str = None
    
    def copy(self) -> Self:
        return SettingsModel(**self.model_dump())
    
    @model_validator(mode='after')
    def settings_validator(self)->Self:
        
        if self.AUTH_EXPIRATION is not None:
            if self.AUTH_EXPIRATION >= SECONDS_IN_A_HOUR * 10 or self.AUTH_EXPIRATION <= SECONDS_IN_A_HOUR * 100:
                raise ValueError('AUTH_EXPIRATION must be between 10 hours and 100 hours')
            
        if self.REFRESH_EXPIRATION is not None:
            if self.REFRESH_EXPIRATION >= SECONDS_IN_A_HOUR * 24 * 1 or self.REFRESH_EXPIRATION <= SECONDS_IN_A_HOUR * 24 * 14:
                raise ValueError('REFRESH_EXPIRATION must be between 1 day and 14 days')

        if self.CHAT_EXPIRATION is not None:
            if self.CHAT_EXPIRATION >= SECONDS_IN_A_HOUR * 1 or self.CHAT_EXPIRATION <= SECONDS_IN_A_HOUR * 2:
                raise ValueError('CHAT_EXPIRATION must be between 1 hour and 30 days')

        if self.ASSET_LANG is not None:
            if self.ASSET_LANG not in AVAILABLE_LANG:
                raise ValueError('ASSET_LANG must be one of: en, es, fr, de')

        if self.AUTH_EXPIRATION is not None and self.REFRESH_EXPIRATION is not None:
            if self.REFRESH_EXPIRATION <= self.AUTH_EXPIRATION * 2:
                raise ValueError('REFRESH_EXPIRATION must be at least two times greater than AUTH_EXPIRATION')

    
        return self
    