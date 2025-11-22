from dataclasses import dataclass
from enum import Enum
from pydantic import BaseModel, PrivateAttr, field_validator, model_validator
from typing import Any,Iterable, Literal, Optional, Self, TypedDict, NotRequired
from app.classes.scheduler import Scheduler, CrontabSchedulerModel, DateTimeSchedulerModel, RRuleSchedulerModel, SolarSchedulerModel, TimedeltaSchedulerModel
from app.definition._error import BaseError
from pydantic import BaseModel
from datetime import timedelta,datetime


###############################################################################################################
###############################################################################################################


class CeleryTaskNotFoundError(BaseError):
    ...

class CeleryTaskNameNotExistsError(BaseError):
    ...

class CelerySchedulerOptionError(BaseError):
    ...


###############################################################################################################
###############################################################################################################


class TaskHeaviness(Enum):
    VERY_LIGHT = 1  # Minimal effort required
    LIGHT = 2       # Some effort, but not demanding
    MODERATE = 3    # Balanced workload
    HEAVY = 4       # Challenging and requires focus
    VERY_HEAVY = 5  # Extremely demanding and time-consuming

COST_LEVELS = {
    TaskHeaviness.VERY_LIGHT: 0.1,
    TaskHeaviness.LIGHT: 0.5,
    TaskHeaviness.MODERATE: 1.0,
    TaskHeaviness.HEAVY: 2.0,
    TaskHeaviness.VERY_HEAVY: 5.0
}


def Compute_Weight(cost:float,heaviness:TaskHeaviness):
    return cost * COST_LEVELS[heaviness]


class TaskType(Enum):
    RRULE = 'rrule'
    SOLAR = 'solar'
    CRONTAB = 'crontab'
    TIMEDELTA = 'timedelta'
    DATETIME = 'datetime'
    NOW = 'now'


TaskTypeLiteral = Literal['rrule','solar','crontab','now','timedelta','datetime']
SenderType =Literal['raw','subs','contact']
AlgorithmType = Literal['normal','mix','worker','route']


SCHEDULER_MODEL_MAP: dict[TaskType, type[Scheduler]] = {
    TaskType.RRULE: RRuleSchedulerModel,
    TaskType.SOLAR: SolarSchedulerModel,
    TaskType.CRONTAB: CrontabSchedulerModel,
    TaskType.TIMEDELTA: TimedeltaSchedulerModel,
    TaskType.DATETIME: DateTimeSchedulerModel,
}

###############################################################################################################
###############################################################################################################

class SubContentBaseModel(BaseModel):
    as_contact:bool = False
    index:int |None = None
    will_track:bool = False
    sender_type:SenderType='raw'
    _contact:str|list[str]|None =PrivateAttr(default=[])

class SubContentIndexBaseModel(BaseModel):
    index:int |None = None

class CeleryOptionModel(BaseModel):
    countdown:Optional[int]= None
    expires:Optional[DateTimeSchedulerModel] = None
    _retry:Optional[bool]= PrivateAttr(default=False)
    _queue:Optional[str]= PrivateAttr(default=None)
    _ignore_result:bool=PrivateAttr(default=True)


    def model_dump(self, *, mode = 'python', include = None, exclude = None, context = None, by_alias = False, exclude_unset = False, exclude_defaults = False, exclude_none = False, round_trip = False, warnings = True, serialize_as_any = False):
        vals = super().model_dump(mode=mode, include=include, exclude=exclude, context=context, by_alias=by_alias, exclude_unset=exclude_unset, exclude_defaults=exclude_defaults, exclude_none=exclude_none, round_trip=round_trip, warnings=warnings, serialize_as_any=serialize_as_any)
        return {
            'retry':self._retry,
            'queue':self._queue,
            'ignore_result':self._ignore_result,
            **vals
        }

class SchedulerModel(BaseModel):
    filter_error:bool=True
    schedule_name:Optional[str] = None
    task_name:str
    task_type:TaskType
    task_option:CeleryOptionModel
    scheduler_option: Optional[dict] = None
    priority:Literal[1,2,3,4,5] = 1
    content: Any | list[Any]
    _heaviness: Any = None
    _errors:dict[int,dict|str] = PrivateAttr({})
    _message:dict[int,str] = PrivateAttr({})
    _scheduler:Scheduler = PrivateAttr(None)
        
    @field_validator('content')
    def check_content(cls,content:Any):
        if not isinstance(content,list):
            return [content]

        return content

    @model_validator(mode='after')
    def validate_model(self:Self):
        if self.task_type == TaskType.NOW:
            return self
        if not self.scheduler_option:
            raise CelerySchedulerOptionError("Scheduler option must be provided for task types other than 'now'")
        self._scheduler = SCHEDULER_MODEL_MAP[self.task_type].model_validate(self.scheduler_option)._object
        return self

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


###############################################################################################################
###############################################################################################################

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


