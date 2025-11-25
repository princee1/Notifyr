from app.classes.auth_permission import FuncMetaData
from app.classes.cost_definition import SMSCostDefinition
from app.definition._cost import TaskCost
from app.depends.class_dep import TwilioTracker
from app.manager.task_manager import TaskManager
from app.models.sms_model import SMSCustomSchedulerModel, SMSTemplateSchedulerModel


class SMSCost(TaskCost):
    
    def compute_cost(self,func_meta:FuncMetaData, scheduler:SMSCustomSchedulerModel|SMSTemplateSchedulerModel, taskManager:TaskManager, tracker:TwilioTracker):
        definition:SMSCostDefinition = func_meta['cost_definition']
        total_content, total_recipient = super().compute_cost(func_meta,scheduler, taskManager, tracker)