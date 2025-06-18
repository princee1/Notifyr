from typing import List, Self
from pydantic import BaseModel, field_validator, model_validator
from app.classes.celery import SubContentBaseModel, SchedulerModel
from app.utils.validation import url_validator

class OnGoingBaseSMSModel(SubContentBaseModel):
    from_:str = None
    to:str | list[str]

    @model_validator(mode="after")
    def to_validator(self:Self)->Self:
        if self.sender_type == 'subs':
            return self
        if isinstance(self.to,str):
            self.to = [self.to]
        return self
        

class OnGoingTemplateSMSModel(OnGoingBaseSMSModel):
    data:dict

class OnGoingSMSModel(OnGoingBaseSMSModel):
    body:str
    media_url:List[str] = []

    @field_validator('media_url')
    def check_url(cls,media_url:list[str]):
        media_url = media_url[0:10]
        return [url for url in media_url if url_validator(url)]
 


class SMSCustomSchedulerModel(SchedulerModel):
    content: OnGoingSMSModel | list[OnGoingSMSModel]

class SMSTemplateSchedulerModel(SchedulerModel):
    content: OnGoingTemplateSMSModel |list[OnGoingTemplateSMSModel]


###############################################             ################################################

class SMSStatusModel(BaseModel):
    MessageSid:str
    AccountSid:str
    To:str
    From:str
    SmsSid:str
    SmsStatus:str
    MessageStatus:str
    twilio_tracking_id:str = None

