from typing import Dict,TypedDict,Any
from dataclasses import  dataclass
from enum import Enum

class ErrorCode(Enum):
    ...

class BaseError(Exception):
    
    def __init__(self, *args):
        super().__init__(*args)

    @property
    def detail(self):
        ...
    @property
    def to_args(self):
        ...