
from pydantic import BaseModel


class OTPModel(BaseModel):
    otp:str
    to:str
    from_:str=None
    brand:str = None
    expiry:int
    type:str

    