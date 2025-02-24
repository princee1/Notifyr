
from pydantic import BaseModel


class OTPModel(BaseModel):
    otp:str
    to:str
    from_:str
    brand:str = None
    expiry:int
    type:str

    