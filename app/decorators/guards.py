from app.definition._utils_decorator import Guard
from app.container import Get, InjectInMethod
from app.services.assets_service import AssetService
from app.services.celery_service import BackgroundTaskService, CeleryService
from app.services.config_service import ConfigService
from app.utils.constant  import HTTPHeaderConstant
from app.classes.celery import TaskHeaviness, TaskType,SchedulerModel

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

class AssetGuard(Guard):
    #TODO If a route allowed a certain type asset
    def __init__(self,allowed_path=[],options=[]):
        super().__init__()
        self.assetService = Get(AssetService)       
        self.configService = Get(ConfigService)
        self.options = options
        self.allowed_path = allowed_path

    def guard(self,template:str):
        ...

        
class TaskWorkerGuard(Guard):
    #TODO Check before hand if the background task and the workers are available to do some job
    def __init__(self, heaviness:TaskHeaviness=None):
        super().__init__()
        self.celeryService = Get(CeleryService)
        self.bckgroundTaskService = Get(BackgroundTaskService)
        self.heaviness = heaviness
    
    def guard(self,scheduler:SchedulerModel):
        task_heaviness:TaskHeaviness = scheduler.heaviness
        ...