from dataclasses import dataclass
from typing import Any, List, Optional
from typing_extensions import TypedDict,Dict
from pydantic import BaseModel
from app.classes.celery import TaskTypeLiteral
from app.definition._error import BaseError
from dataclasses import dataclass, field


@dataclass
class ReceiptItem:
    description: str
    amount: int
    quantity: int = 1
    subtotal: int = field(init=False)

    def __post_init__(self) -> None:
        self.subtotal = self.amount * self.quantity

class Receipt(TypedDict):
    request_id: str
    credit: Any
    definition: Optional[str]
    created_at: str
    items: List[ReceiptItem]
    purchase_total: int
    refund_total: int
    total: int
    balance_before: Optional[int]
    balance_after: Optional[int]


class CostCredits(TypedDict):
    email:int
    sms:int
    phone:int
    contact:int
    client:int
    profile:int
    link:int

class CostRules(TypedDict):
    bonus_percentage_on_topup: float

    default_credit_reset: bool
    carry_over_allowed: bool
    
    credit_overdraft_allowed: bool

    auto_block_on_zero_credit: bool
    overdraft_ratio_allowed:float

    retry_allowed: bool
    track_allowed:bool

class SimpleTaskCostDefinition(TypedDict):
    __api_usage_cost__:int
    __rate_limit__:str
    __credit_key__:str
    __mount__:bool
    __copy__:dict | str

class TaskCostDefinition(SimpleTaskCostDefinition):
    __max_free_content__:int
    __max_free_recipient__:int
    __content_extra_cost__:int
    __recipient_extra_cost__:int
    __priority_cost__: int
    __tracking_cost__:int
    __retry_cost__:int
    __allowed_task_option__:list[str]
    __task_type_cost__:Dict[TaskTypeLiteral,int]


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

    attachement_cost:Attachement
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