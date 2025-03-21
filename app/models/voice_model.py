from pydantic import BaseModel, field_validator
from app.utils.validation import url_validator

class BaseVoiceCallModel(BaseModel):
    to:str
    from_:str =None
    timeout:int
    record:bool = True
    time_limit:int


class OnGoingCustomVoiceCallModel(BaseVoiceCallModel):
    body:str    

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