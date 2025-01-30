from app.definition._utils_decorator import Guard
from app.container import InjectInMethod
from app.services.config_service import ConfigService
from app.utils.constant  import HTTPHeaderConstant
from app.classes.celery import TaskName

class TwilioGuard(Guard):
    ...


class PlivoGuard(Guard):
    ...


class CeleryTaskGuard(Guard):
    def __init__(self,task_names:list[TaskName]):
        super().__init__()
        self.task_names = task_names
        
    