from app.classes.auth_permission import FuncMetaData
from app.classes.cost_definition import PhoneCostDefinition
from app.definition._cost import TaskCost
from app.depends.class_dep import TwilioTracker
from app.models.call_model import CallCustomSchedulerModel, CallTemplateSchedulerModel, CallTwimlSchedulerModel
from app.services.task_service import TaskManager


class CallCost(TaskCost):
    
    def compute_cost(self, func_meta:FuncMetaData, scheduler:CallTemplateSchedulerModel|CallTwimlSchedulerModel|CallCustomSchedulerModel, taskManager:TaskManager, tracker:TwilioTracker):
        definition:PhoneCostDefinition=func_meta['cost_definition']
        return super().compute_cost(func_meta, scheduler, taskManager, tracker)