from typing import Any, List, Self
from pydantic import BaseModel, field_validator, model_validator
from app.utils.validation import language_code_validator,url_validator

class Verbs(BaseModel):
    type:str
    value:str |int

    @model_validator(mode="after")
    def check_value(self)->Self:
        match self.type:
            case 'say':
                if not self.value:
                    if len(self.value) > 500:
                        raise ValueError("Text length should not exceed 500 characters")
                    self.value = self.value.strip()
                else:
                    raise ValueError("Text value cannot be empty")
            case 'play':
                if not url_validator(self.value):
                    raise ValueError("Invalid URL format")

            case 'pause':
                if not isinstance(self.value, int):
                    raise ValueError("Pause value must be an integer")
            case _:
                raise ValueError("Invalid type for value")
        return self

class GatherConfig(BaseModel):
    timeout:int =5
    language:str = "en-US"
    finishOnKey:str = "#"

    @field_validator("language")
    def check_language(cls,language:str) -> str:
        if not language_code_validator(language):
            raise ValueError("Invalid language code")
        return language

class DTMFConfig(GatherConfig):
    numDigits:int |None = 6

class SpeechConfig(GatherConfig):
    ...

class OTPModel(BaseModel):
    to:str
    from_:str=None
    content:Any
    # otp:str
    # brand:str = None

class GatherDtmfContent(DTMFConfig):
    remove_base_instruction:bool = False
    add_instructions:List[Verbs] = []
    add_finish_key_phrase:bool = True
    no_input_instruction:str = None

    def check_instructions_len(cls, instructions:str) -> str:
        if len(instructions) > 500:
            raise ValueError("Instructions length should not exceed 500 characters")
        return instructions
    
class GatherDtmfOTPModel(OTPModel):
    content:GatherDtmfContent
    otp:str=None
    service:str = None