from typing import Self, Type, List, Dict, Any, Optional, TypedDict
from fastapi import Depends, Request
from app.classes.auth_permission import FuncMetaData
from app.classes.cost_definition import Receipt, ReceiptItem, SimpleTaskCostDefinition, TaskCostDefinition
from app.container import Get
from app.depends.class_dep import TrackerInterface
from app.depends.dependencies import get_request_id
from app.manager.task_manager import TaskManager
from app.services.cost_service import REDIS_CREDIT_KEY_BUILDER, CostService
from app.utils.helper import PointerIterator
from app.classes.celery import SchedulerModel
from datetime import datetime



costService: CostService = Get(CostService)

class Cost:

    rules = costService.rules
    
    def __init__(self, request_id: str=Depends(get_request_id)):
        self.purchase_cost: int = 0
        self.refund_cost: int = 0

        self.request_id = request_id

        self.balance_before: Optional[int] = None
        self.created_at: datetime = datetime.now()
        self.purchase_items: List[ReceiptItem] = []
        self.refund_items:List[ReceiptItem] = []

        self.credit_key=...
        self.definition_name=None
        
    def purchase(self,description:str,amount:int,quantity=1):
        item = ReceiptItem(description,amount,quantity)
        self.purchase_items.append(item)
        self.purchase_cost += item.amount * item.quantity

    def reset_bill(self):
        self.purchase_items.clear()
        self.refund_items.clear()

        self.purchase_cost = 0
        self.refund_cost = 0
    
    def refund(self,description:str,amount:int,quantity=1):
        item = ReceiptItem(description,amount,quantity)
        self.refund_items.append(item)
        self.refund_cost += item.subtotal

    def generate_receipt(self)-> Receipt:
        return {
            "request_id": self.request_id,
            "credit":REDIS_CREDIT_KEY_BUILDER(self.credit_key),
            "definition": self.definition_name,
            "created_at": self.created_at.isoformat(),
            "p-items": [
                {"description": it.description, "amount": it.amount, "quantity": it.quantity, "subtotal":it.subtotal}
                for it in self.purchase_items
            ],
            "r-items":[
                {"description": it.description, "amount": it.amount, "quantity": it.quantity, "subtotal":it.subtotal}
                for it in self.refund_items
            ],
            "purchase_total": self.purchase_cost,
            "refund_total": self.refund_cost,
            "total":self.purchase_cost - self.refund_cost,
            "balance_before": self.balance_before,
            "balance_after": self.balance_before - (self.purchase_cost - self.refund_cost),
        }

class DataCost(Cost):
    
    def init(self,default_price:int,credit_key:str,definition_name=None):
        self.default_price = default_price
        self.credit_key = credit_key
        self.definition_name = definition_name

    def pre_purchase(self):
        self.purchase(self.credit_key,self.default_price)

    
    def post_purchase(self,result:Any):
        self.purchase(self.credit_key,self.default_price)
    
    
    def post_refund(self,result:Any):
        self.refund(self.credit_key,self.default_price)

class SimpleTaskCost(Cost):

    def register_state(self, balance_before: int):
        self.balance_before = balance_before

    def register_meta_key(self,func_meta:FuncMetaData):
        self.credit_key=func_meta['cost_definition']["__credit_key__"]
        self.definition_name = func_meta["cost_definition_name"]

    def compute_cost(self,func_meta:FuncMetaData):
        definition:SimpleTaskCostDefinition=func_meta['cost_definition']
        self.purchase('api_usage',amount=definition['__api_usage_cost__'])


class TaskCost(SimpleTaskCost):

    pointer: PointerIterator = None

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
            self.purchase("content_extra", definition['__content_extra_cost__'],content_diff)
        if recipient_diff>0:
            self.purchase("recipient_extra", amount=definition['__recipient_extra_cost__'],quantity=recipient_diff)        
        if tracker.will_track:
            self.purchase("tracking", amount=definition['__tracking_cost__'],quantity=total_recipient)
        if taskManager.meta.get('retry', False):
            self.purchase(description="retry", amount=definition['__retry_cost__'], quantity=total_recipient)
        
        self.purchase(description="priority", amount=int(definition['__priority_cost__'] / scheduler.task_option.priority))
        self.purchase(description=f"task_type:{scheduler.task_type}", amount=definition['__task_type_cost__'].get(scheduler.task_type.value, 1))
        self.purchase('api_usage',amount=definition['__api_usage_cost__'])
        return total_content, total_recipient


        
###################################################             ################################################33333

###################################################             ################################################33333
