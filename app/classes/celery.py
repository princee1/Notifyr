from enum import Enum
from pydantic import BaseModel
from typing import Any,Iterable, Optional, TypedDict
from app.definition._error import BaseError


class CeleryTaskNotFoundError(BaseError):
    ...

class CeleryTaskNameNotExistsError(BaseError):
    ...


class TaskName(Enum):
    ...


class Scheduler(BaseModel):
    ...


class CeleryTask(TypedDict):
    task_name:str
    task_type:str
    task_option:Optional[dict] = {}
    args: tuple[Any] | Iterable[Any] = ()
    kwargs: dict[str,Any] = {}


