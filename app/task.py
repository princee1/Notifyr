import sys
from typing import Callable
from celery import Celery,shared_task
from celery.result import AsyncResult
from app.classes.celery import CeleryTaskNameNotExistsError
from app.services.config_service import ConfigService
from app.services.email_service import EmailSenderService
from app.container import Get, build_container, Register
from app.utils.prettyprint import PrettyPrinter_
from app.classes.celery import CeleryTaskNotFoundError,SCHEDULER_RULES
from app.classes.celery import  CeleryTask, SchedulerModel
from app.definition._service import Service, ServiceClass, ServiceStatus
from app.utils.helper import generateId
from redbeat  import RedBeatSchedulerEntry
from app.utils.helper import generateId
import datetime as dt
import shutil

exe_path = shutil.which("celery").replace(".EXE","")
##############################################           ##################################################

if sys.argv[0] == exe_path:
    PrettyPrinter_.message('Building container for the celery worker')
    build_container(False)

##############################################           ##################################################

CELERY_MODULE_NAME = __name__

def compute_name(t:str)-> str:
    
    name = task_name(t)
    if name not in TASK_REGISTRY:
        raise CeleryTaskNameNotExistsError(name)
    return name

def task_name(t):
    return f'{CELERY_MODULE_NAME}.{t}'


TASK_REGISTRY:dict[str,Callable] = {}
try:

    configService: ConfigService = Get(ConfigService)
    backend_url =  configService.CELERY_BACKEND_URL
    message_broker_url=  configService.CELERY_MESSAGE_BROKER_URL
except :
    backend_url = "redis://localhost/0"
    message_broker_url="redis://localhost/0"

##############################################           ##################################################

@ServiceClass
class CeleryService(Service):
    _celery_app = ...
    _task_registry = TASK_REGISTRY
    def __init__(self,configService:ConfigService):
        Service.__init__(self)
        self.configService = configService
        

    def trigger_task_from_scheduler(self,scheduler:SchedulerModel,*args,**kwargs):
        celery_task = scheduler.model_dump(mode='python',exclude={'content'})
        celery_task: CeleryTask = CeleryTask(args=args,kwargs=kwargs,**celery_task)
        return self._trigger_task(celery_task,scheduler.schedule_name)


    def trigger_task_from_task(self,celery_task:CeleryTask,schedule_name:str= None):
        return self._trigger_task(celery_task,schedule_name)

    def _trigger_task(self,celery_task:CeleryTask,schedule_name:str=None):
        schedule_id = schedule_name if schedule_name is not None else generateId(25)
        c_type = celery_task['task_type']
        t_name = celery_task['task_name']
        now = dt.datetime.now()
        result = {
            'message': f'[{now}] - Task [{t_name}] received successfully'
        }
        
        if c_type == 'now':
            task_result = self._task_registry[t_name].delay(*celery_task['args'],**celery_task['kwargs'])
            result.update({'task_id':task_result.id,'type':'task'})
            return result

        options = celery_task['task_option']
        if c_type == 'once':
            task_result = self._task_registry[t_name].apply_async(**options,args=celery_task['args'],kwargs=celery_task['kwargs'])
            result.update({'task_id':task_result.id,'type':'task'})
            return task_result.id

        schedule = SCHEDULER_RULES[c_type]
        schedule = schedule(**options)
        entry = RedBeatSchedulerEntry(schedule_id,t_name,schedule,args=celery_task['args'],kwargs=celery_task['kwargs'])
        entry.save()
        result.update({'task_id':schedule_id,'type':'schedule'})
        return result

    def cancel_task(self,task_id,force=False):
        result = AsyncResult(task_id, app=self._celery_app)

        if result.state in ["PENDING", "RECEIVED"]:
            result.revoke(terminate=False)

        elif result.state in ["STARTED"]:
            if force:
                result.revoke(terminate=True, signal="SIGTERM")

    def delete_schedule(self,schedule_id:str):
        try:
            schedule_id = f'redbeat:{schedule_id}'
            entry = RedBeatSchedulerEntry.from_key(schedule_id,app=self._celery_app)
            entry.delete()
        except KeyError:
            raise CeleryTaskNotFoundError

    def seek_schedule(self,schedule_id:str):
        try:
            schedule_id = f'redbeat:{schedule_id}'
            entry = RedBeatSchedulerEntry.from_key(schedule_id,app=self._celery_app)
            return {
                'total_run_count':entry.total_run_count,
                'due_at':entry.due_at,
                'schedule':entry.schedule,
                'last_run_at':entry.last_run_at
            }
        except KeyError:
            raise CeleryTaskNotFoundError

    def seek_result(self, task_id: str):
        try:
            result = AsyncResult(task_id, app=self._celery_app)
            response = {
                'task_id': result.id,
                'status': result.status,
                'result': result.result,
                'traceback': result.traceback,
                'date_done': result.date_done,
                'successful': result.successful()
            }
            return response
        except KeyError:
            raise CeleryTaskNotFoundError
    
    def build(self):
        ...

Register(CeleryService)

##############################################           ##################################################


celery_app = Celery('celery_app',
            backend=backend_url,
            broker=message_broker_url
        )

celery_app.conf.update(task_serializer='pickle', accept_content=['pickle'])

# Enable RedBeat Scheduler
celery_app.conf.beat_scheduler = "redbeat.RedBeatScheduler"
celery_app.conf.redbeat_redis_url = backend_url
celery_app.conf.timezone = "UTC"

celery_app.autodiscover_tasks(['app.ressources'], related_name='email_ressource')

CeleryService._celery_app =celery_app

def RegisterTask(name:str=None):
    def decorator(task:Callable):

        TASK_REGISTRY[task_name(task.__qualname__)] = celery_app.task(name=name)(task)
        return task
    return decorator

def SharedTask(name:str=None):
    def decorator(task:Callable):
        TASK_REGISTRY[task_name(task.__qualname__)] = shared_task(name=name)(task)
        return task
    return decorator

@RegisterTask()
def task_send_template_mail(data, meta, images):
    emailService:EmailSenderService = Get(EmailSenderService)
    return emailService.sendTemplateEmail(data, meta, images)
    
@RegisterTask()
def task_send_custom_mail(content, meta, images, attachment):
    emailService:EmailSenderService = Get(EmailSenderService)
    return emailService.sendCustomEmail(content, meta, images, attachment)


##############################################           ##################################################
