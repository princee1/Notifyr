import sys
from typing import Callable
from celery import Celery,shared_task
from celery.result import AsyncResult
from app.classes.celery import CeleryTaskNameNotExistsError
from app.services.config_service import ConfigService
from app.services.email_service import EmailSenderService
from app.container import Get, build_container
from app.utils.prettyprint import PrettyPrinter_
import shutil

##############################################           ##################################################


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

celery_app = Celery('celery_app',
            backend=backend_url,
            broker=message_broker_url
        )

#celery_app.conf.update(task_serializer='pickle', accept_content=['pickle'])

# Enable RedBeat Scheduler
celery_app.conf.beat_scheduler = "redbeat.RedBeatScheduler"
celery_app.conf.redbeat_redis_url = backend_url
celery_app.conf.timezone = "UTC"

celery_app.autodiscover_tasks(['app.services'], related_name='celery_service')
celery_app.autodiscover_tasks(['app.ressources'], related_name='email_ressource')
celery_app.autodiscover_tasks(['app.server'], related_name='middleware')


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
