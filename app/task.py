import functools
import sys
from typing import Any, Callable
from typing_extensions import Literal
from celery import Celery, shared_task
from celery.result import AsyncResult
from app.classes.celery import CeleryTaskNameNotExistsError, TaskHeaviness
from app.services.config_service import ConfigService,CeleryEnv
from app.services.email_service import EmailSenderService
from app.container import Get, build_container
from app.services.security_service import JWTAuthService
from app.services.twilio_service import SMSService, CallService
from app.utils.prettyprint import PrettyPrinter_
import shutil
from flower import VERSION


##############################################           ##################################################

IS_SERVER_SCOPE=True
exe_path = shutil.which("celery").replace(".EXE", "")
##############################################           ##################################################

c_env:CeleryEnv = 'none'
if sys.argv[0] == exe_path:
    PrettyPrinter_.message('Building container for the celery worker')
    IS_SERVER_SCOPE = False
    c_env = sys.argv[3]
    ConfigService.set_celery_env(c_env)
    PrettyPrinter_.message(c_env)
    build_container(False)
        
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
configService.isServerScope = IS_SERVER_SCOPE

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

celery_app.autodiscover_tasks(['app.services'], related_name='celery_service')
celery_app.autodiscover_tasks(
    ['app.ressources'], related_name='email_ressource')
celery_app.autodiscover_tasks(['app.server'], related_name='middleware')


@functools.wraps(celery_app.task)
def RegisterTask(heaviness: TaskHeaviness, **kwargs):
    def decorator(task: Callable):

        TASK_REGISTRY[task_name(task.__qualname__)] = {
            'heaviness': heaviness,
            'task': celery_app.task(**kwargs)(task)
        }

        return task
    return decorator


@functools.wraps(shared_task)
def SharedTask(heaviness: TaskHeaviness, **kwargs):
    def decorator(task: Callable):
        TASK_REGISTRY[task_name(task.__qualname__)] = {
            'heaviness':heaviness,
            'task':shared_task(**kwargs)(task)
        }
        
        return task
    return decorator

##############################################           ##################################################


@RegisterTask(TaskHeaviness.LIGHT)
def task_send_template_mail(data, meta, images):
    emailService: EmailSenderService = Get(EmailSenderService)
    return emailService.sendTemplateEmail(data, meta, images)


@RegisterTask(TaskHeaviness.LIGHT)
def task_send_custom_mail(content, meta, images, attachment):
    emailService: EmailSenderService = Get(EmailSenderService)
    return emailService.sendCustomEmail(content, meta, images, attachment)

@RegisterTask(TaskHeaviness.LIGHT)
def task_send_custom_sms(messages):
    smsService:SMSService = Get(SMSService)
    return smsService.send_custom_sms(messages)

@RegisterTask(TaskHeaviness.LIGHT)
def task_send_template_sms(messages):
    smsService:SMSService = Get(SMSService)
    return smsService.send_template_sms(messages)

@RegisterTask(TaskHeaviness.LIGHT)
def task_send_template_voice_call(result,content):
    callService:CallService = Get(CallService)
    return callService.send_template_voice_call(result,content)

@RegisterTask(TaskHeaviness.LIGHT)
def task_send_twiml_voice_call(url,details):
    callService:CallService = Get(CallService)
    return callService.send_twiml_voice_call(url,details)
    
    
@RegisterTask(TaskHeaviness.LIGHT)
def task_send_custom_voice_call(body,details):
    callService:CallService = Get(CallService)
    return callService.send_custom_voice_call(body,details)

##############################################           ##################################################
