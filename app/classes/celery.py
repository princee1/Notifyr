from enum import Enum
from ordered_set import OrderedSet
from pydantic import BaseModel, field_validator
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


class TaskType(Enum):
    RRULE = 'rrule'
    SOLAR = 'solar'
    CRONTAB = 'crontab'
    #TIMEDELTA = 'timedelta'
    #DATETIME = 'datetime'
    NOW = 'now' # direct task call
    ONCE= 'once' # direct task call

TaskTypeLiteral = Literal['rrule','solar','crontab','now','once']  #'timedelta','datetime'
class SchedulerModel(BaseModel):
    schedule_name:Optional[str] = None
    timezone:Optional[str] = None
    task_name:str
    task_type:TaskTypeLiteral
    task_option:Optional[dict] ={}
    priority:Literal[1,2,3,4,5] = 1
    queue_name:Optional[str] = None
    content:Any
    
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


class TaskHeaviness(Enum):
    VERY_LIGHT = 1  # Minimal effort required
    LIGHT = 2       # Some effort, but not demanding
    MODERATE = 3    # Balanced workload
    HEAVY = 4       # Challenging and requires focus
    VERY_HEAVY = 5  # Extremely demanding and time-consuming

