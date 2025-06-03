from typing import List
from pydantic import BaseModel, field_validator
from app.utils.validation import url_validator

class OnGoingBaseSMSModel(BaseModel):
    from_:str = None
    to:str

class OnGoingTemplateSMSModel(OnGoingBaseSMSModel):
    data:dict

class OnGoingSMSModel(OnGoingBaseSMSModel):
    body:str
    media_url:List[str] = []

    @field_validator('media_url')
    def check_url(cls,media_url:list[str]):
        media_url = media_url[0:10]
        return [url for url in media_url if url_validator(url)]
 
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

