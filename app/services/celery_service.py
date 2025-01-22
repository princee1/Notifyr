from dataclasses import dataclass
from app.definition._service import Service, ServiceClass
from .config_service import ConfigService
from app.interface.threads import InfiniteThreadInterface
from app.celery_task import celery_app # TODO try to dynamically decorate the celery tasks
import asyncio
from typing import Any, Callable, Iterable, TypedDict

@dataclass
class TaskCallback(TypedDict):
    func:Callable[...,Any]
    args: tuple[Any] | Iterable[Any]
    kwargs: dict[str,Any]
    

@ServiceClass
class CeleryService(Service,InfiniteThreadInterface):
    def __init__(self,configService:ConfigService,):
        Service.__init__(self)
        InfiniteThreadInterface.__init__(self)
        self.configService = configService
        self.taskCallbacks: list[TaskCallback] = []

    def registerTask(self,func:Callable[...,Any],*args:Any,**kwargs:Any):
        self.taskCallbacks.append({'func':func,'args':args,'kwargs':kwargs})
    



