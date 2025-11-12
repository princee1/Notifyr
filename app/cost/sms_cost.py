from app.classes.auth_permission import FuncMetaData
from app.classes.cost_definition import SMSCostDefinition
from app.definition._cost import TaskCost


class SMSCost(TaskCost):
    
    def compute_cost(self,func_meta:FuncMetaData, scheduler, taskManager, tracker):
        definition:SMSCostDefinition = func_meta['cost_definition']
        total_content, total_recipient = super().compute_cost(func_meta,scheduler, taskManager, tracker)