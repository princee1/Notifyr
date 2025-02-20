
from pydantic import BaseModel


class OTPModel(BaseModel):
    otp:str
    name:str
    phone:str
    