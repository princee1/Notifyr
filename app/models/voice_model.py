from pydantic import BaseModel, field_validator
from app.utils.validation import url_validator,language_code_validator

class BaseVoiceCallModel(BaseModel):
    to:str
    from_:str =None
    timeout:int
    record:bool = True
    time_limit:int = 60


class OnGoingCustomVoiceCallModel(BaseVoiceCallModel):
    body:str
    voice:str="alice"
    language:str = "en-US"
    loop:int = 1

    @field_validator('language')
    def validate_language(cls, language: str):
        if not language_code_validator(language):
            raise ValueError(f"Invalid language code: {language}")
        return language

class OnGoingTwimlVoiceCallModel(BaseVoiceCallModel):
    url:str

    @field_validator('url')
    def check_twiml_url(cls,url:str):
        if not url_validator(url):
            raise ValueError('Invalid URL Address')
        return url
    
###############################################             ################################################

class CallStatusModel(BaseModel):
    CallSid:str
    RecordingSid:str
    Duration:int=None
    CallDuration:int=None
    RecordingDuration:int=None
    Direction:str
    Timestamp:str
    AccountSid:str
    CallStatus:str
    ToCity:str
    SipResponse:int
    To:str
    From:str
    SequenceNumber:str