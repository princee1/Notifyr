from typing import TypedDict
import operator
from aiohttp_retry import Any, Callable
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

