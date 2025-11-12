from typing import Self, Type, List, Dict, Any, Optional
from fastapi import Depends, Request
from app.classes.auth_permission import FuncMetaData
from app.classes.cost_definition import SimpleTaskCostDefinition, TaskCostDefinition
from app.container import Get
from app.depends.class_dep import TrackerInterface
from app.depends.dependencies import get_request_id
from app.services.cost_service import CostService
from app.services.task_service import TaskManager
from app.utils.helper import PointerIterator
from app.classes.celery import SchedulerModel

from dataclasses import dataclass, field
from datetime import datetime
import logging


@dataclass
class ReceiptItem:
    description: str
    amount: float
    quantity: int = 1


costService: CostService = Get(CostService)

class Cost:

    rules = costService.rules
    pointer: PointerIterator = None

    def __init__(self, request_id: str=Depends(get_request_id)):
        self.purchase_cost: float = 0.0
        self.refund_cost: float = 0.0

        self.request_id = request_id

        self.balance_before: Optional[int] = None
        self.created_at: datetime = datetime.now()
        self.items: List[ReceiptItem] = []
        
    def register_state(self, balance_before: int):
        self.balance_before = balance_before

    def register_meta_key(self,func_meta:FuncMetaData):
        self.credit_key=func_meta['cost_definition']["__credit_key__"]
        self.definition_name = func_meta["cost_definition_name"]

    def add_item(self,description:str,amount:int,quantity=1):
        item = ReceiptItem(description,amount,quantity)
        self.items.append(item)
        self.purchase_cost += item.amount * item.quantity

    def compute_cost(self,) -> int:
        ...

    def refund(self, c=0):
        self.refund_cost += c
        return c

    @property
    def receipt(self):
        return self.to_dict()

    @staticmethod
    def _compute_max_free_features(max_value, extra_cost, current_value):
        diff = current_value - max_value
        return 0 if diff <= 0 else diff * extra_cost
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "credit_key":self.credit_key,
            "definition_name": self.definition_name,
            "created_at": self.created_at.isoformat(),
            "items": [
                {"description": it.description, "amount": it.amount, "quantity": it.quantity, "subtotal":it.amount*it.quantity}
                for it in self.items
            ],
            "purchase_total": self.purchase_cost,
            "refund_total": self.refund_cost,
            "balance_before": self.balance_before,
            "balance_after": self.balance_before - (self.purchase_cost - self.refund_cost),
        }


class TaskCost(Cost):

    def compute_cost(self,func_meta:FuncMetaData, scheduler: SchedulerModel, taskManager: TaskManager, tracker: TrackerInterface):
        total_recipient = 0
        definition:TaskCostDefinition = func_meta['cost_definition']

        for content in scheduler.content:
            ptr = self.pointer.ptr(content)
            total_recipient += len(ptr.get_val())

        total_content = len(scheduler.content)

        content_diff = total_content - definition['__max_free_content__']
        recipient_diff = total_recipient - definition['__max_free_recipient__']

        if content_diff>0:
            self.add_item("content_extra", definition['__content_extra_cost__'],content_diff)
        if recipient_diff>0:
            self.add_item("recipient_extra", amount=definition['__recipient_extra_cost__'],quantity=recipient_diff)        
        if tracker.will_track:
            self.add_item("tracking", amount=definition['__tracking_cost__'],quantity=total_recipient)
        if taskManager.meta.get('retry', False):
            self.add_item(description="retry", amount=definition['__retry_cost__'], quantity=total_recipient)
        
        self.add_item(description="priority", amount=definition['__priority_cost__'] / max(1, scheduler.priority))
        self.add_item(description=f"task_type:{scheduler.task_type}", amount=definition['__task_type_cost__'].get(scheduler.task_type, 1))
        self.add_item('api_usage',amount=definition['__api_usage_cost__'])
        return total_content, total_recipient


class DataCost:
    ...

class SimpleCost(Cost):
    
    def compute_cost(self,func_meta:FuncMetaData):
        definition:SimpleTaskCostDefinition=func_meta['cost_definition']
        self.add_item('api_usage',amount=definition['__api_usage_cost__'])
        
###################################################             ################################################33333

###################################################             ################################################33333


def inject_cost_definition(cost_definition: str):

    def callback(request: Request):
        request.state.cost_definition = cost_definition
        return

    return callback
