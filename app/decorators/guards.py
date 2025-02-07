from app.definition._utils_decorator import Guard
from app.container import InjectInMethod
from app.services.config_service import ConfigService
from app.utils.constant  import HTTPHeaderConstant
from app.classes.celery import TaskType,SchedulerModel

class TwilioGuard(Guard):
    ...


class PlivoGuard(Guard):
    ...


class CeleryTaskGuard(Guard):
    def __init__(self,task_names:list[str],task_types:list[TaskType]=None):
        super().__init__()
        self.task_names = task_names
        self.task_types = task_types
    
    def guard(self,scheduler:SchedulerModel):
        if scheduler.task_name not in self.task_names:
            return False,f'The task: {scheduler.task_name} is  not permitted for this route'
        
        if self.task_types != None and scheduler.task_name not in self.task_types:
            return False,f'The task_type: {scheduler.task_type} is not permitted for this route'
        
        return True,''

       
        
    