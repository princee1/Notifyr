from typing import Self
from pydantic import BaseModel, model_validator

from app.classes.template import AVAILABLE_LANG
from app.utils.constant import SettingDBConstant,DEFAULT_SETTING

SECONDS_IN_A_HOUR = 3600

class GlobalVarModel(BaseModel):
    model_config = {
        "extra": "allow"
    }


min_auth = 10 * SECONDS_IN_A_HOUR
max_auth = 100 * SECONDS_IN_A_HOUR

min_refresh = 1 * SECONDS_IN_A_HOUR * 24
max_refresh = 14 * SECONDS_IN_A_HOUR * 24

min_chat = SECONDS_IN_A_HOUR * 1
max_chat = SECONDS_IN_A_HOUR * 2


contact_token_expi = DEFAULT_SETTING[SettingDBConstant.CONTACT_TOKEN_EXPIRATION_SETTING]

max_contact_expiration = contact_token_expi *1.8

api_expiration = DEFAULT_SETTING[SettingDBConstant.API_EXPIRATION_SETTING]


class SettingsModel(BaseModel):
    AUTH_EXPIRATION: int = None
    REFRESH_EXPIRATION: int = None
    CHAT_EXPIRATION: int = None
    ASSET_LANG: str = None
    CONTACT_TOKEN_EXPIRATION:int =None
    API_EXPIRATION:int =None
    
    def copy(self) -> Self:
        return SettingsModel(**self.model_dump())
    
    @model_validator(mode='after')
    def settings_validator(self)->Self:
        
        if self.AUTH_EXPIRATION is not None:
            if not (self.AUTH_EXPIRATION >= min_auth and self.AUTH_EXPIRATION <= max_auth):
                raise ValueError(f'AUTH_EXPIRATION must be between 10 hours({min_auth}) and 100 hours({max_auth})')

        if self.REFRESH_EXPIRATION is not None:
            if not (self.REFRESH_EXPIRATION >= min_refresh and self.REFRESH_EXPIRATION <= max_refresh):
                raise ValueError(f'REFRESH_EXPIRATION must be between 1 day({min_refresh}) and 14 days({max_refresh})')

        if self.CHAT_EXPIRATION is not None:
            if not (self.CHAT_EXPIRATION >= min_chat and self.CHAT_EXPIRATION <= max_chat):
                raise ValueError(f'CHAT_EXPIRATION must be between 1 hour({min_chat}) and 2 hours({max_chat})')

        if self.ASSET_LANG is not None:
            if self.ASSET_LANG not in AVAILABLE_LANG:
                raise ValueError('ASSET_LANG must be one of: en, es, fr, de')

        if self.AUTH_EXPIRATION is not None and self.REFRESH_EXPIRATION is not None:
            if self.REFRESH_EXPIRATION <= self.AUTH_EXPIRATION * 2:
                raise ValueError('REFRESH_EXPIRATION must be at least two times greater than AUTH_EXPIRATION')
            
        
        if self.CONTACT_TOKEN_EXPIRATION is not None:
            if not (self.CONTACT_TOKEN_EXPIRATION >= contact_token_expi and self.CONTACT_TOKEN_EXPIRATION <= max_contact_expiration):
                raise ValueError(f'CONTACT_TOKEN_EXPIRATION must be in [{contact_token_expi} , {max_contact_expiration}] ')

        if self.API_EXPIRATION is not None:
            if not (self.API_EXPIRATION >= api_expiration*0.3 and self.API_EXPIRATION <= api_expiration*1.3):
                raise ValueError(f'API_EXPIRATION must be in [{api_expiration *.3} , {api_expiration *1.3} ]')
    
        return self
    