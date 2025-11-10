from typing import Type
from fastapi import Request
from app.container import Get
from app.definition._error import BaseError
from app.services.cost_service import CostService


class Cost:

    def __init__(self,cost_key:str,c=0):
        self.cost_key = cost_key
        self.purchase_cost = c
        self.refund_cost = 0
        self.request_id = None
        self.costService = Get(CostService)
        self.balance_before = ...
        self.balance_after = ...    

    def register_request_id(self,request_id:str):
        self.request_id = request_id

    def compute_cost(self,)->int:
        ...
    
    def refund(self,):
        ...
    
    def register_state(self,balance_before:int):
        self.balance_before = balance_before

    @property
    def receipt(self):
        ...
    


def InjectCost(key:str,cost_type:Type[Cost],start_cost:int=0):
    return lambda :cost_type(key,start_cost)


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