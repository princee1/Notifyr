from app.classes.cost import EmailCostDefinition
from app.classes.template import HTMLTemplate
from app.definition._cost import Cost
from app.depends.class_dep import TrackerInterface
from app.models.email_model import EmailTemplateSchedulerModel,  CustomEmailSchedulerModel  
from app.services.task_service import TaskManager
from app.utils.helper import PointerIterator


class EmailCost(Cost):

    pointer = PointerIterator('meta.To',)
    def __init_subclass__(cls):
        setattr(cls,'pointer',cls.pointer)
        return super().__init_subclass__()
    
    def compute_cost(self,scheduler:CustomEmailSchedulerModel|EmailTemplateSchedulerModel,taskManager:TaskManager,tracker:TrackerInterface,template:HTMLTemplate=None):
        definition:EmailCostDefinition = self.definition
        attachement = definition['attachement']
        total_content,total_recipient= self._scheduler_compute_cost(scheduler,taskManager,tracker)
        
        if isinstance(scheduler,CustomEmailSchedulerModel):
            ...
        
        elif isinstance(scheduler,EmailTemplateSchedulerModel):
            mimeCost = 0
            for content in scheduler.content:
                mimeCost+= definition['mime'].get(content.mimeType,0)
            
            self.add_item('mime',mimeCost)