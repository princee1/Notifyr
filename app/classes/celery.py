from dataclasses import dataclass
from enum import Enum
from types import NoneType
from fastapi import HTTPException,status
from ordered_set import OrderedSet
from pydantic import BaseModel, PrivateAttr, field_validator
from typing import Any,Iterable, Literal, Optional, TypedDict, NotRequired
from app.definition._error import BaseError
from pydantic import BaseModel
import time
from datetime import timedelta,datetime
from redbeat.schedules import rrule
from celery.schedules import solar
from celery.schedules import crontab
from inspect import signature

class CeleryTaskNotFoundError(BaseError):
    ...

class CeleryTaskNameNotExistsError(BaseError):
    ...

class CelerySchedulerOptionError(BaseError):
    ...

class TaskHeaviness(Enum):
    VERY_LIGHT = 1  # Minimal effort required
    LIGHT = 2       # Some effort, but not demanding
    MODERATE = 3    # Balanced workload
    HEAVY = 4       # Challenging and requires focus
    VERY_HEAVY = 5  # Extremely demanding and time-consuming


class TaskType(Enum):
    RRULE = 'rrule'
    SOLAR = 'solar'
    CRONTAB = 'crontab'
    #TIMEDELTA = 'timedelta'
    #DATETIME = 'datetime'
    NOW = 'now' # direct task call
    ONCE= 'once' # direct task call

TaskTypeLiteral = Literal['rrule','solar','crontab','now','once']  #'timedelta','datetime'
SenderType =Literal['raw','subs','contact']
AlgorithmType = Literal['normal','mix','worker_focus','route-focus']

class SubContentBaseModel(BaseModel):
    as_contact:bool = False
    index:int |None = None
    will_track:bool = False
    sender_type:SenderType='raw'
    _contact:str|list[str]|None =PrivateAttr(default=[])

class SubContentIndexBaseModel(BaseModel):
    index:int |None = None

class SchedulerModel(BaseModel):
    filter_error:bool=True
    schedule_name:Optional[str] = None
    timezone:Optional[str] = None
    task_name:str
    task_type:TaskTypeLiteral
    task_option:Optional[dict] ={}
    priority:Literal[1,2,3,4,5] = 1
    queue_name:Optional[str] = None
    content: Any | list[Any]
    heaviness: Any = None
    _errors:dict[int,dict|str] = PrivateAttr({})
    _message:dict[int,str] = PrivateAttr({})
    
    

    @field_validator('heaviness')
    def check_heaviness(cls, heaviness:Any):
        if heaviness is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail={'message':'heaviness property should not be set'})
    
    @field_validator('content')
    def check_content(cls,content:Any):
        if not isinstance(content,list):
            return [content]

        return content
    
SCHEDULER_RULES:dict[str,type] = {
    'rrule': rrule,
    'solar':solar,
    'crontab':crontab,
    #'timedelta':timedelta,
    #'datetime':datetime,    
}

SCHEDULER_VALID_KEYS = {k:OrderedSet(signature(r).parameters.keys()) for k,r in SCHEDULER_RULES.items() }

class CeleryTask(TypedDict):
    task_name:str
    task_type:TaskTypeLiteral
    task_option:Optional[dict] = None
    args: tuple[Any] | Iterable[Any] = ()
    kwargs: dict[str,Any] = {}
    priority:Literal[1,2,3,4,5] = 1
    queue_name:Optional[str] = None
    schedule_name:Optional[str] = None
    task_id:Optional[str] = None
    heaviness:TaskHeaviness

@dataclass
class s:
    heaviness: TaskHeaviness

class TaskRetryError(BaseError):
    def __init__(self,error, *args):
        super().__init__(*args)
        self.error=error


UNSUPPORTED_TASKS = 549


WARNING_MESSAGE = {
    UNSUPPORTED_TASKS:{
    "name":"unsupported_task",
    "message":   "This task is not supported in the current environment, we now used the celery worker to run this task"
}}

def add_warning_messages(warning_code:int, scheduler:SchedulerModel,index=None):

    if warning_code not in WARNING_MESSAGE.keys():
        raise ValueError(f"Warning code {warning_code} is not defined")
    if warning_code in scheduler._message:
        return

    scheduler._message[warning_code]= WARNING_MESSAGE[warning_code].copy()
    scheduler._message[warning_code]['index'] = index