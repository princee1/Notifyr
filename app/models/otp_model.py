
from typing import Any
from pydantic import BaseModel


class OTPModel(BaseModel):
    to:str
    from_:str=None
    content:Any
    # otp:str
    # brand:str = None
    # expiry:int

    