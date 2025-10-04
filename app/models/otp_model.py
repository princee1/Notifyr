from typing import Any, List, Self
from pydantic import BaseModel, PrivateAttr, field_validator, model_validator
from app.utils.validation import language_code_validator,url_validator
from string import digits
from app.utils.helper import letter_to_number

parse = lambda v: v if v in digits else letter_to_number[v.upper()]

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
    speechTimeout:int|None=None
    profanityFilter:bool=True
    hints:str=""
    speechModel:str|None=None
    

class OTPModel(BaseModel):
    to:str
    from_:str=PrivateAttr(None)
    content:Any
    # otp:str
    # brand:str = None

class GatherInstruction(BaseModel):
    remove_base_instruction:bool = False
    add_instructions:List[Verbs] = []
    add_finish_key_phrase:bool = True
    no_input_instruction:str = None

    @field_validator("no_input_instruction")
    def check_instructions_len(cls, instructions:str) -> str:
        if len(instructions) > 500:
            raise ValueError("Instructions length should not exceed 500 characters")
        return instructions
    

class GatherOTPBaseModel(OTPModel):
    content:GatherConfig
    otp:str
    service:str = None
    instruction:GatherInstruction

class GatherDtmfOTPModel(GatherOTPBaseModel):
    content:DTMFConfig
    
    @model_validator(mode="after")
    def check_len_otp(self) -> Self:
        try:
            self.otp = "".join([ parse(l)  for l in self.otp])
        except KeyError:
            raise ValueError("Symbol not permitted")
        
        if len(self.otp) != self.content.numDigits:
            raise ValueError(f"OTP length should not exceed {self.content.numDigits} characters")
        return self
    
class GatherSpeechOTPModel(GatherOTPBaseModel):
    content: SpeechConfig

