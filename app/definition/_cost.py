from typing import Self, Type
from fastapi import Request
from app.classes.cost import SimpleTaskCostDefinition, TaskCostDefinition
from app.container import Get
from app.depends.class_dep import TrackerInterface
from app.depends.dependencies import get_request_id
from app.services.cost_service import CostService
from app.services.task_service import TaskManager
from app.utils.helper import PointerIterator
from app.classes.celery import SchedulerModel


costService:CostService = Get(CostService)

class Cost:

    rules = costService.rules
    pointer:PointerIterator = None

    def __init__(self,request_id:str,cost_definition:str):
        self.purchase_cost = 0
        self.refund_cost = 0

        self.request_id = request_id
        self.cost_definition_key = cost_definition
        self.definition:SimpleTaskCostDefinition | TaskCostDefinition = costService.costs_definition.get(cost_definition)

        self.balance_before:int = ...

    def register_state(self,balance_before:int):
        self.balance_before = balance_before

    def _scheduler_compute_cost(self,scheduler:SchedulerModel,taskManager:TaskManager,track:TrackerInterface):
        total_recipient =0 
        for content in scheduler.content:
            ptr = self.pointer.ptr(content)
            total_recipient+=len(ptr.get_val())
        
        total_content = len(scheduler.content) 

        content_cost = self._compute_max_free_features(self.definition['__max_free_content__'],self.definition['__content_extra_cost__'],total_content)
        recipient_cost = self._compute_max_free_features(self.definition['__max_free_recipient__'],self.definition['__recipient_extra_cost__',total_recipient])
        priority_cost = self.definition['__priority_cost__']/scheduler.priority
        tracking_cost = 0 if not track.will_track else total_recipient*self.definition['__tracking_cost__']
        retry_cost = 0 if not taskManager.meta.get('retry',False) else total_recipient *self.definition['__retry_cost__']
        task_cost = self.definition['__task_type_cost__'].get(scheduler.task_type,1)

        self.purchase_cost += (content_cost + recipient_cost +priority_cost +tracking_cost + retry_cost + task_cost)

        return total_content,total_recipient

    def compute_cost(self,)->int:
        ...
    
    def refund(self,c=0):
        ...
    
    @property
    def receipt(self):
        ...
    
    @staticmethod
    def _compute_max_free_features(max_value,extra_cost,current_value):
        diff = current_value - max_value
        return 0 if diff <= 0 else diff * extra_cost

    
class DataCost:
    ...

class SimpleCost:
    ...


def inject_cost_definition(cost_definition:str):

    def callback(request:Request):
        request.state.cost_definition = cost_definition
        return 
    return callback

def InjectCost(cost_type:Type[Cost]):
    
    async def callback(request:Request):
        request_id = await get_request_id(request)
        cost_definition = request.state.cost_definition
        return cost_type(request,cost_definition)
    
    return callback