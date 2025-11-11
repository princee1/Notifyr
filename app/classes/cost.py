from typing import Dict, TypedDict
from app.classes.celery import TaskTypeLiteral
from app.definition._error import BaseError


class CostCredits(TypedDict):
    email:int
    sms:int
    phone:int
    contact:int
    client:int
    profile:int
    link:int

class CostRules(TypedDict):
    default_credit_reset: bool
    carry_over_allowed: bool
    bonus_percentage_on_topup: float
    credit_overdraft_allowed: bool
    auto_block_on_zero_credit: bool
    extra_recipient_allowed: bool
    retry_allowed: bool


class SimpleTaskCostDefinition(TypedDict):
    __api_usage_cost__:int
    __rate_limit__:str
    __credit_key__:str
    __mount__:bool
    __copy__:dict | str

class TaskCostDefinition(SimpleTaskCostDefinition):
    __max_content__:int
    __max_recipient__:int
    __recipient_extra_cost__:int
    __priority_cost__: int
    __tracking_cost__:int
    __retry_cost__:int
    __allowed_task_option__:list[str]
    __task_option__:Dict[TaskTypeLiteral,int]


class EmailCostDefinition(TaskCostDefinition):
    class Attachement(TypedDict):
        attachement_free_count :int
        attachement_per_extra: int
        attachement_allowed:bool = True
        attachement_free_size:int
        attachement_cost_per_extra_kb: int
    
    class Mime(TypedDict):
        html:int
        text:int
        both:int

    attachement:Attachement
    mime:Mime
    email_free_size:int
    email_size_per_extra_kb: int
    


class SMSCostDefinition(TaskCostDefinition):
    class Body(TypedDict):
        max_content_size: int
        max_medial_url: int
        body_cost_per_extra_size: int

class PhoneCostDefinition(TaskCostDefinition):
    class Time(TypedDict):
        max_free_time:int
        allowed_extra_time:bool= True
        time_cost_per_extra_second:int

    time:Time

class ObjectCostDefinition(TypedDict):
    count: int
    max_size: 10000
    max_version_count:int
    allowed_extra_size:bool = True
    object_size_extra_per_kb: int


class CostException(BaseError):
    ...

class PaymentFailedError(CostException):
    """Payment gateway failure."""

class InsufficientCreditsError(CostException):
    """Not enough credits to complete the purchase."""

class InvalidPurchaseRequestError(CostException):
    """Missing or invalid purchase data."""

class CreditDeductionFailedError(CostException):
    """Redis optimistic locking / transaction conflict."""

class CurrencyNotSupportedError(CostException):
    """Currency code is unsupported."""

class ProductNotFoundError(CostException):
    """Requested product does not exist."""