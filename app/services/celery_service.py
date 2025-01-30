from app.classes.celery import CeleryTask, CeleryTaskNotFoundError
from app.definition._service import Service, ServiceClass
from .config_service import ConfigService
from app.interface.threads import InfiniteAsyncInterface
from app.task import task_send_custom_mail,task_send_template_mail
from app.utils.helper import generateId

@ServiceClass
class CeleryService(Service,InfiniteAsyncInterface):

    def __init__(self,configService:ConfigService,):
        Service.__init__(self)
        InfiniteAsyncInterface.__init__(self)
        self.configService = configService
        self.cross_reference_id:dict[str,str] = {}

    def register_task(self,celery_task: CeleryTask)->str:
        

        task_id = ...
        return self._reference_task(task_id)

    def _reference_task(self, task_id):
        cross_id = generateId(25)
        self.cross_reference_id[cross_id] = task_id
        return cross_id
    
    def get_task_id(self,reference_id:str):
        task_id = self.cross_reference_id.get(reference_id,None)
        if task_id == None:
            raise CeleryTaskNotFoundError
        return task_id

