from datetime import datetime
from typing import ClassVar, Self, TypedDict
import operator
from aiohttp_retry import Any, Callable
from pydantic import Field
from pyparsing import Optional
from typing_extensions import Literal

Operator = Literal["$eq","$ne","$gt","$ge","$lt","$le","$in","$nin"]
Method = Literal['simple-number-validation','advanced-number-validation']

mapping = {
        "$eq": "==",
        "$ne": "!=",
        "$gt": ">",
        "$ge": ">=",
        "$lt": "<",
        "$le": "<=",
    }

OPS:dict[Operator,Callable[[int,int],bool]]= {
    "$eq": operator.eq,
    "$ne": operator.ne,
    "$gt": operator.gt,
    "$ge": operator.ge,
    "$lt": operator.lt,
    "$le": operator.le,
    "$in": lambda a, b: a in b,
    "$nin": lambda a, b: a not in b,
}

def simple_number_validation(value, condition:dict[Operator,int]):
    if not isinstance(condition, dict):
        raise ValueError("Condition must be a dict")
    for op, target in condition.items():
        if op not in OPS:
            raise ValueError(f"Unsupported operator {op}")
        if not OPS[op](value, target):
            return False
    return True

class MongoCondition(TypedDict):
    force:bool
    rule:dict |Any
    filter:dict
    method:Method


from beanie import Document

class BaseDocument(Document):
        
    alias: str
    description: Optional[str] = Field(default=None,min_length=0,max_length=400)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    last_modified: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    version: int = 1

    _unique_indexes: ClassVar[list[str]] = []
    _condition:ClassVar[Optional[MongoCondition]] = None
    _collection:ClassVar[Optional[str]] = None
    _primary_key:ClassVar[str]  = 'alias'

    async def update_meta_profile(self,base_doc:Self):
        base_doc.last_modified =  datetime.utcnow().isoformat()
        base_doc.version+=1
        await base_doc.save()
        

    class Settings:
        abstract=True