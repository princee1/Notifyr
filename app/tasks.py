import sys
from typing import Any, Callable
from celery import Celery
from app.classes.celery import CeleryTaskNameNotExistsError, TaskHeaviness
from app.services.config_service import CELERY_EXE_PATH, CeleryMode, ConfigService,CeleryEnv
from app.container import Get, build_container,__DEPENDENCY
from app.utils.prettyprint import PrettyPrinter_
from flower import VERSION
from celery import Task
from app.services import *
from celery.exceptions import SoftTimeLimitExceeded,MaxRetriesExceededError,TaskRevokedError,QueueNotFound


##############################################           ##################################################

if sys.argv[0] == CELERY_EXE_PATH:
    PrettyPrinter_.message(f'Building container for the celery {ConfigService._celery_env.value}')
    if ConfigService._celery_env != CeleryMode.worker:
        build_container(False,dep=[ConfigService])
    else:
        dependency = __DEPENDENCY.copy()
        dependency.remove(AssetService)
        dependency.remove(HealthService)
        dependency.remove(CostService)
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

celery_app.conf.result_backend_transport_options = {
    'global_keyprefix': 'notifyr_task_',
    'retry_policy': {
       'timeout': 5.0
    }
}
celery_app.conf.task_store_errors_even_if_ignored = True
celery_app.conf.task_ignore_result = True

celery_app.conf.broker_transport_options = {
    'priority_steps': list(range(3)),
    'sep': ':',
    'queue_order_strategy': 'priority',
}
celery_app.conf.worker_soft_shutdown_timeout = 120.0
celery_app.conf.worker_enable_soft_shutdown_on_idle = True
celery_app.conf.task_create_missing_queues = False


if ConfigService._celery_env == CeleryMode.none:
    celery_app.autodiscover_tasks(['app.services'], related_name='celery_service')
    celery_app.autodiscover_tasks(['app.ressources'], related_name='email_ressource')
    celery_app.autodiscover_tasks(['app.server'], related_name='middleware')
    celery_app.autodiscover_tasks(['app.signals'], related_name='middleware')

if configService._celery_env == CeleryMode.worker:
    import app.signals

##############################################           ##################################################

def RegisterTask(heaviness: TaskHeaviness, retry_policy=None,rate_limit:str=None,time_limit:dict[str,int]=None,name:str=None):
    def decorator(task: Callable):
        kwargs = {}
        kwargs['bind'] =True
        kwargs['retry_policy'] = retry_policy
        kwargs['rate_limit'] = rate_limit
        kwargs['time_limit'] = time_limit

        _name = name if name is not None else task_name(task.__qualname__)
        kwargs['name'] = _name
        TASK_REGISTRY[name] = {
            'heaviness': heaviness,
            'task': celery_app.task(**kwargs)(task)
        }

        return task
    return decorator

##############################################           ##################################################


@RegisterTask(TaskHeaviness.LIGHT)
def task_send_template_mail(self:Task,*args,**kwargs):
    print(self.request)

    emailService: EmailSenderService = Get(EmailSenderService),
    email_profile = kwargs.get('email_profile',None)
    emailMiniService=emailService.MiniServiceStore.get(email_profile)
    return emailMiniService.sendTemplateEmail(*args,**kwargs)


@RegisterTask(TaskHeaviness.LIGHT)
def task_send_custom_mail(self:Task,*args,**kwargs):
    emailService: EmailSenderService = Get(EmailSenderService)
    email_profile = kwargs.get('email_profile',None)
    emailMiniService=emailService.MiniServiceStore.get(email_profile)
    return emailMiniService.sendCustomEmail(*args,**kwargs)

#============================================================================================================#

@RegisterTask(TaskHeaviness.LIGHT)
def task_send_custom_sms(self:Task,*args,**kwargs):
    smsService:SMSService = Get(SMSService)
    return smsService.send_custom_sms(*args,**kwargs)

@RegisterTask(TaskHeaviness.LIGHT)
def task_send_template_sms(self:Task,*args,**kwargs):
    smsService:SMSService = Get(SMSService)
    return smsService.send_template_sms(*args,**kwargs)

#============================================================================================================#

@RegisterTask(TaskHeaviness.LIGHT)
def task_send_template_voice_call(self:Task,*args,**kwargs):
    callService:CallService = Get(CallService)
    return callService.send_template_voice_call(*args,**kwargs)

@RegisterTask(TaskHeaviness.LIGHT)
def task_send_twiml_voice_call(self:Task,*args,**kwargs):
    callService:CallService = Get(CallService)
    return callService.send_twiml_voice_call(*args,**kwargs)
    
@RegisterTask(TaskHeaviness.LIGHT)
def task_send_custom_voice_call(self:Task, *args,**kwargs):
    callService:CallService = Get(CallService)
    return callService.send_custom_voice_call(*args,**kwargs)

#============================================================================================================#

@RegisterTask(TaskHeaviness.LIGHT)
def task_send_webhook(self:Task,*args,**kwargs):
    webhookService:WebhookService = Get(WebhookService)
    webhook_profile = kwargs.get('webhook_profile',None)
    webhookMiniService=webhookService.MiniServiceStore.get(webhook_profile)
    return webhookMiniService.deliver(*args,**kwargs)

##############################################           ##################################################
