from datetime import datetime
from typing import ClassVar, List, Self, TypedDict,Optional, Any, Callable
import operator
import uuid
from pydantic import BaseModel, Field
from typing_extensions import Literal
from app.definition._error import BaseError

Operator = Literal["$eq","$ne","$gt","$ge","$lt","$le","$in","$nin"]
Method = Literal['simple-number-validation','advanced-number-validation']

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
    validation:Literal['match','exist'] # whether we check the condition satisfaction if the value exist(all) or match
    force:bool # if the document does not have the filter value, force it
    rule:dict |Any # rule to respect in regards of how many document have 
    filter:dict # value to filter the search
    method:Method # method to compare the rule too


def validate_filter(mc:MongoCondition,p_dump):

    if mc['bypass_validate']:
        return True
    
    try:
        for k,v in mc['filter'].items():
            
            match mc['validation']:

                case 'match':
                    if v == p_dump[k]:
                        continue
                    else:
                        return False
                
                case 'exist':
                    if v != None:
                        continue
                    else:
                        return False
                
    except KeyError:
        return False
    return True

from beanie import Document
from app.utils.helper import uuid_v1_mc

class BaseDocument(Document):
    id: str = Field(default_factory=lambda: f"{uuid_v1_mc(1)}")

    alias: str
    description: Optional[str] = Field(default=None,min_length=0,max_length=400)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    last_modified: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    version: int = 1

    _unique_indexes: ClassVar[list[str]] = []
    _condition:ClassVar[Optional[List[MongoCondition]]] = None
    _collection:ClassVar[Optional[str]] = None
    _primary_key:ClassVar[str]  = 'alias'

    async def update_meta(self):
        self.last_modified =  datetime.utcnow().isoformat()
        self.version+=1
        await self.save()
        
    async def update_content(self,body:BaseModel):
        _body  = body.model_dump()
        for k,v in _body.items():
            if v is not None:
                try:
                    getattr(self,k)
                    setattr(self,k,v)
                except:
                    continue

    class Settings:
        abstract=True