from typing import Self
from pydantic import BaseModel, model_validator
from phonenumbers import country_code_for_region, region_code_for_country_code,region_codes_for_country_code
from app.utils.helper import phone_parser
from app.utils.validation import phone_number_validator

class PhoneModel(BaseModel):
    country_code:str | int = None
    phone_number:str

    @model_validator(mode='after')
    def phone_validation(self)->Self:
        
        phone_number = phone_parser(self.phone_number,self.country_code)
        if not phone_number_validator(phone_number):
            raise ValueError(f'Phone number format is not valid: {phone_number}')
        self.phone_number = phone_number
        return self



