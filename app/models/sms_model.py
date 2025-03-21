
from typing import List
from pydantic import BaseModel


class OnGoingBaseSMSModel(BaseModel):
    from_:str = None
    to:str

class OnGoingTemplateSMSModel(OnGoingBaseSMSModel):
    data:dict

class OnGoingSMSModel(OnGoingBaseSMSModel):
    body:str
    media_url:List[str] = []
 

###############################################             ################################################

class SMSStatusModel(BaseModel):
    MessageSid:str
    AccountSid:str
    To:str
    From:str
    SmsSid:str
    SmsStatus:str
    MessageStatus:str
