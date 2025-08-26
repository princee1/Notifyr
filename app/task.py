import functools
import sys
from typing import Any, Callable
from celery import Celery, shared_task
from app.classes.celery import CeleryTaskNameNotExistsError, TaskHeaviness
from app.services.config_service import CELERY_EXE_PATH, CeleryMode, ConfigService,CeleryEnv
from app.container import Get, build_container,__DEPENDENCY
from app.utils.prettyprint import PrettyPrinter_
from flower import VERSION
from celery import Task
from app.services import *


##############################################           ##################################################

if sys.argv[0] == CELERY_EXE_PATH:
    PrettyPrinter_.message(f'Building container for the celery {ConfigService._celery_env.value}')
    if ConfigService._celery_env != CeleryMode.worker:
        build_container(False,dep=[ConfigService])
    else:
        dependency = __DEPENDENCY.copy()
        dependency.remove(AssetService)
        build_container(False,dep=dependency)
        
##############################################           ##################################################

CELERY_MODULE_NAME = __name__


def compute_name(t: str) -> str:

    name = task_name(t)
    if name not in TASK_REGISTRY:
        raise CeleryTaskNameNotExistsError(name)
    return name


def task_name(t):
    return f'{CELERY_MODULE_NAME}.{t}'


TASK_REGISTRY: dict[str, dict[str, Any]] = {}

##############################################           ##################################################

configService: ConfigService = Get(ConfigService)

##############################################           ##################################################

celery_app = Celery('celery_app',
                    backend=configService.CELERY_BACKEND_URL,
                    broker=configService.CELERY_MESSAGE_BROKER_URL,
                    result_expires=configService.CELERY_RESULT_EXPIRES
                    )

# celery_app.conf.update(task_serializer='pickle', accept_content=['pickle'])

# Enable RedBeat Scheduler
celery_app.conf.beat_scheduler = "redbeat.RedBeatScheduler"
celery_app.conf.redbeat_redis_url = configService.CELERY_BACKEND_URL
celery_app.conf.timezone = "UTC"

if ConfigService._celery_env == CeleryMode.none:

    celery_app.autodiscover_tasks(['app.services'], related_name='celery_service')
    celery_app.autodiscover_tasks(
        ['app.ressources'], related_name='email_ressource')
    celery_app.autodiscover_tasks(['app.server'], related_name='middleware')


@functools.wraps(celery_app.task)
def RegisterTask(heaviness: TaskHeaviness, **kwargs):
    def decorator(task: Callable):
        kwargs['bind'] =True
        TASK_REGISTRY[task_name(task.__qualname__)] = {
            'heaviness': heaviness,
            'task': celery_app.task(**kwargs)(task)
        }

        return task
    return decorator


@functools.wraps(shared_task)
def SharedTask(heaviness: TaskHeaviness, **kwargs):
    def decorator(task: Callable):
        kwargs['bind'] =True
        TASK_REGISTRY[task_name(task.__qualname__)] = {
            'heaviness':heaviness,
            'task':shared_task(**kwargs)(task)
        }
        
        return task
    return decorator

##############################################           ##################################################


@RegisterTask(TaskHeaviness.LIGHT)
def task_send_template_mail(self:Task,data, meta, images,contact_id=None):
    emailService: EmailSenderService = Get(EmailSenderService)
    return emailService.select().sendTemplateEmail(data, meta, images,contact_id)


@RegisterTask(TaskHeaviness.LIGHT)
def task_send_custom_mail(self:Task,content, meta, images, attachment,contact_id=None):
    emailService: EmailSenderService = Get(EmailSenderService)
    return emailService.select().sendCustomEmail(content, meta, images, attachment,contact_id)

@RegisterTask(TaskHeaviness.LIGHT)
def task_send_custom_sms(self:Task,messages):
    smsService:SMSService = Get(SMSService)
    return smsService.send_custom_sms(messages)

@RegisterTask(TaskHeaviness.LIGHT)
def task_send_template_sms(self:Task,messages):
    smsService:SMSService = Get(SMSService)
    return smsService.send_template_sms(messages)

@RegisterTask(TaskHeaviness.LIGHT)
def task_send_template_voice_call(self:Task,result,content):
    callService:CallService = Get(CallService)
    return callService.send_template_voice_call(result,content)

@RegisterTask(TaskHeaviness.LIGHT)
def task_send_twiml_voice_call(self:Task,url,details):
    callService:CallService = Get(CallService)
    return callService.send_twiml_voice_call(url,details)
    
    
@RegisterTask(TaskHeaviness.LIGHT)
def task_send_custom_voice_call(self:Task,body,details):
    callService:CallService = Get(CallService)
    return callService.send_custom_voice_call(body,details)

##############################################           ##################################################
