from typing import Dict, Optional,TypedDict,Any
from dataclasses import  dataclass
from enum import Enum

class ErrorCode(Enum):
    ...

class ErrorDetails(TypedDict):
    message:str
    details:Any
    error_code:int | ErrorCode
    reason: Optional[list[str]] 
    solutions :Optional[list[str]] 

class BaseError(Exception):
    
    def __init__(self, *args):
        super().__init__(*args)

    @property
    def detail(self):
        ...
    @property
    def to_args(self):
        ...


class ServerFileError(BaseError):
    
    def __init__(self, filename,status_code,headers=None):
        self.filename = filename
        self.status_code = status_code
        self.headers = headers
        super().__init__((filename,status_code,headers))