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