import functools
import sys
from typing import Callable
from celery import Celery,shared_task
from app.services.config_service import ConfigService
from app.services.email_service import EmailSenderService
from app.container import Get, build_container
from app.utils.prettyprint import PrettyPrinter_



if 'worker' in sys.argv or 'beat' in sys.argv:
    PrettyPrinter_.message('Building container for the celery worker')
    build_container(False)

MODULE_NAME= __name__ 
def task_name(t:str)-> str:f'{MODULE_NAME}.{t}'

TASK_REGISTRY:dict[str,Callable] = {}

configService: ConfigService = Get(ConfigService)

celery_app = Celery('celery_app',
            backend=configService.CELERY_BACKEND_URL,
            broker=configService.CELERY_MESSAGE_BROKER_URL
        )

celery_app.conf.update(task_serializer='pickle', accept_content=['pickle'])

# Enable RedBeat Scheduler
celery_app.conf.beat_scheduler = "redbeat.RedBeatScheduler"
celery_app.conf.redbeat_redis_url = configService.CELERY_BACKEND_URL
celery_app.conf.timezone = "UTC"

celery_app.autodiscover_tasks(['app.services'], related_name='celery_service')

def RegisterTask(task:Callable):
    TASK_REGISTRY[task.__qualname__] = task
    return celery_app.task(task)

def SharedTask(task:Callable):
    TASK_REGISTRY[task.__qualname__] = task
    return shared_task(task)
    

@RegisterTask
def task_send_template_mail(data, meta, images):
    emailService:EmailSenderService = Get(EmailSenderService)
    return emailService.sendTemplateEmail(data, meta, images)
    
@RegisterTask
def task_send_custom_mail(content, meta, images, attachment):
    emailService:EmailSenderService = Get(EmailSenderService)
    return emailService.sendCustomEmail(content, meta, images, attachment)

