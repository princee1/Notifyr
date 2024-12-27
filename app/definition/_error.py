from typing import Dict,TypedDict,Any
from dataclasses import  dataclass

class BaseError(Exception):
    
    def __init__(self, *args):
        super().__init__(*args)

    @property
    def detail(self):
        ...
    @property
    def to_args(self):
        ...