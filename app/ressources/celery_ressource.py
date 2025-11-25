from app.container import InjectInMethod
from app.definition._ressource import BaseHTTPRessource, HTTPRessource
from app.services.celery_service import CeleryService
from app.services.config_service import ConfigService
from app.services.task_service import TaskService


@HTTPRessource('celery-control')
class CeleryRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,celeryService:CeleryService,configService:ConfigService,taskService:TaskService):
        self.celeryService = celeryService
        self.configService = configService
        self.taskService = taskService


    