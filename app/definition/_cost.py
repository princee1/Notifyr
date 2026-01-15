from typing import Self, Type, List, Dict, Any, Optional, TypedDict
from app.classes.auth_permission import AuthPermission, FuncMetaData
from app.classes.cost_definition import Bill, BillItem, SimpleTaskCostDefinition, TaskCostDefinition
from app.services.cost_service import CostService
from app.container import Get
from app.utils.helper import PointerIterator
from datetime import datetime
from app.utils.globals import APP_MODE,ApplicationMode

if APP_MODE == ApplicationMode.server:
    from app.depends.class_dep import TrackerInterface
    from fastapi import Depends, Request, Response
    from app.depends.dependencies import get_auth_permission, get_request_id
    from app.manager.task_manager import TaskManager
    from app.classes.celery import SchedulerModel


costService: CostService = Get(CostService)

class Cost:

    rules = costService.rules
    
    if APP_MODE == ApplicationMode.server:
        
        def __init__(self,request_id: str=Depends(get_request_id),authPermission:AuthPermission|None=Depends(get_auth_permission)):
            if authPermission == None:
                username='default'
            else:
                username = authPermission['client_username']
            self.__inner__init__(request_id,username)

        @staticmethod
        def inject_cost_info(response:Response,bill:Bill,credit:str,_total=0):
            
            current_balance = bill['balance_after']
            total = bill['total']
            definition_name = bill.get('definition',None)

            if definition_name:
                response.headers.append('X-Definition',definition_name)

            response.headers.append('X-Credit-Name',credit)
            response.headers.append('X-Current-Balance',str(current_balance))
            response.headers.append('X-Total-Cost',str(total+_total))
            
    else:
        def  __init__(self,request_id:str,issuer:str):
            self.__inner__init__(request_id, issuer)

    def __inner__init__(self, request_id, issuer):
        self.purchase_cost: int = 0
        self.refund_cost: int = 0
        self.last_total:int = 0
        self.issuer = issuer
        self.request_id = request_id

        self.balance_before: Optional[int] = None
        self.created_at: datetime = datetime.now()
        self.purchase_items: List[BillItem] = []
        self.refund_items:List[BillItem] = []

        self.credit_key=...
        self.definition_name=None

        self.indexes:dict[int,int] = {}
        self.bypass = False
        self.costService = Get(CostService)
        
    def purchase(self,description:str,amount:int,quantity=1):
        item = BillItem(description,int(amount),quantity)
        self.purchase_items.append(item)
        self.purchase_cost += item.amount * item.quantity

    def reset_bill(self,force =False):
        self.purchase_items.clear()
        self.refund_items.clear()
        self.purchase_cost = 0
        self.refund_cost = 0
        
        if force:
            self.last_total = 0
    
    def refund(self,description:str,amount:int,quantity=1):
        item = BillItem(description,int(amount),quantity)
        self.refund_items.append(item)
        self.refund_cost += item.subtotal

    def generate_bill(self)-> Bill:
        return {
            "request_id":self.request_id,
            "issuer":self.issuer,
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
            "balance_before": 0,
            "balance_after": 0,
        }

    def post_payment(self,result:Any):
        ...

class DataCost(Cost):
    
    def init(self,default_price:int,credit_key:str):
        self.default_price = default_price
        self.credit_key = credit_key

    def pre_purchase(self):
        self.purchase(self.credit_key,self.default_price)
    
    def post_purchase(self,result:Any):
        self.purchase(self.credit_key,self.default_price)
      
    def post_refund(self,result:Any):
        self.refund(self.credit_key,self.default_price)
    
    def post_payment(self,result:Any):
        self.refund(self.credit_key,self.default_price)

if APP_MODE == ApplicationMode.server:

    class SimpleTaskCost(Cost):

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
