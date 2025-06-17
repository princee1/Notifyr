from typing import Self
from pydantic import BaseModel, field_validator, model_validator
from app.classes.celery import SubContentBaseModel, SchedulerModel
from app.utils.validation import url_validator,language_code_validator

class BaseVoiceCallModel(SubContentBaseModel):
    to:str
    from_:str =None
    timeout:int
    record:bool = True
    time_limit:int = 60

    @model_validator(mode="after")
    def to_validator(self:Self)->Self:
        if isinstance(self.to,str):
            self.to = [self.to]  
        return self

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


class CallTemplateSchedulerModel(SchedulerModel):
    content: BaseVoiceCallModel | list[BaseVoiceCallModel]


class CallTwimlSchedulerModel(SchedulerModel):
    content: OnGoingTwimlVoiceCallModel |  list[OnGoingTwimlVoiceCallModel]


class CallCustomSchedulerModel(SchedulerModel):
    content: OnGoingCustomVoiceCallModel | list[OnGoingCustomVoiceCallModel]
    
###############################################             ################################################

class CallStatusModel(BaseModel):
    CallSid:str
    RecordingSid:str|None = None
    Duration:int|None=None
    CallDuration:int|None=None
    RecordingDuration:int|None=None
    Direction:str
    Timestamp:str
    AccountSid:str
    CallStatus:str
    ToCity:str
    ToCountry:str|None
    ToState:str|None
    To:str
    From:str
    SequenceNumber:str
    subject_id:str|None = None
    twilio_tracking_id:str = None

class GatherDataModel(BaseModel):
    message:str
    result:bool

class GatherResultModel(BaseModel):
    subject_id:str
    request_id:str
    CallSid:str
    To:str
    data:GatherDataModel
    state:str