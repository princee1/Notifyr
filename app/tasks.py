import functools
from typing import Any, Callable
from celery import Celery
from app.classes.celery import CeleryTaskNameNotExistsError, TaskHeaviness
from app.services.config_service import ConfigService
from app.container import Get, build_container
from app.services import *
from app.utils.globals import APP_MODE, ApplicationMode,CAPABILITIES
from app.utils.prettyprint import PrettyPrinter_
from celery import Task
from app.utils.constant import CeleryConstant
from celery.exceptions import SoftTimeLimitExceeded,MaxRetriesExceededError,TaskRevokedError,QueueNotFound
from celery.worker.control import control_command


##############################################           ##################################################

if  APP_MODE in [ApplicationMode.beat, ApplicationMode.worker]: 
    PrettyPrinter_.message(f'Building container for the celery {APP_MODE.value}')
    build_container()
        
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
redisService  = Get(RedisService)
vaultService = Get(VaultService)
rabbitmqService = Get(RabbitMQService)

backend_url = configService.CELERY_BACKEND_URL(redisService.backend_creds['data']['username'],redisService.backend_creds['data']['password'])

if configService.CELERY_BROKER == 'redis':
    broker_url = configService.CELERY_MESSAGE_BROKER_URL(redisService.broker_creds['data']['username'],redisService.broker_creds['data']['password'])
else:
    broker_url = configService.CELERY_MESSAGE_BROKER_URL(rabbitmqService.db_user,rabbitmqService.db_password)
##############################################           ##################################################

celery_app = Celery('celery_app',
                    backend=backend_url,
                    broker=broker_url,
                    result_expires=configService.CELERY_RESULT_EXPIRES
                    )

# Enable RedBeat Scheduler
celery_app.conf.beat_scheduler = "redbeat.RedBeatScheduler"
celery_app.conf.redbeat_redis_url = backend_url
celery_app.conf.redbeat_key_prefix = f"{CeleryConstant.BACKEND_KEY_PREFIX}redbeat:"
celery_app.conf.timezone = "UTC"

celery_app.conf.result_backend_transport_options = {
    'global_keyprefix': CeleryConstant.REDIS_TASK_ID_RESOLVER(''),
    'retry_policy': {
       'timeout': 5.0
    }
}
celery_app.conf.task_store_errors_even_if_ignored = True
celery_app.conf.task_ignore_result = True

celery_app.conf.worker_soft_shutdown_timeout = 120.0
celery_app.conf.worker_enable_soft_shutdown_on_idle = True
celery_app.conf.task_create_missing_queues = True

if configService.CELERY_BROKER == 'redis':
    celery_app.conf.visibility_timeout = configService.CELERY_VISIBILITY_TIMEOUT
    celery_app.conf.broker_transport_options = {
        'priority_steps': [1,2,3],
        'sep': ':',
        'queue_order_strategy': 'priority',
        "global_keyprefix": CeleryConstant.BROKER_KEY_PREFIX
    }
else:
    celery_app.conf.task_queue_max_priority = 3 # Only rabbit mq

if APP_MODE == ApplicationMode.server:
    celery_app.autodiscover_tasks(['app.services'], related_name='celery_service')
    celery_app.autodiscover_tasks(['app.ressources'], related_name='email_ressource')
    celery_app.autodiscover_tasks(['app.server'], related_name='middleware')
    celery_app.autodiscover_tasks(['app.signals'], related_name='middleware')

if APP_MODE == ApplicationMode.worker:
    import app.signals

##############################################           ##################################################

def RegisterTask(heaviness: TaskHeaviness, retry_policy=None,rate_limit:str=None,acks_late:bool=False):
    def decorator(task: Callable):
        kwargs = {}
        kwargs['bind'] =True
        kwargs['retry_policy'] = retry_policy
        kwargs['rate_limit'] = rate_limit
        #kwargs['acks_late'] = acks_late

        name = task_name(task.__qualname__)

        @functools.wraps(task)
        def wrapper(self:Task,*args,**kwargs):
            return task(*args,**kwargs)

        TASK_REGISTRY[name] = {
            'heaviness': heaviness,
            'task': celery_app.task(**kwargs)(wrapper),
            'raw_task':task,
        }

        return task
    return decorator

################################################## 
# 
# 
# 
###################################################

@control_command(args=[('p', str)],signature='[P=None]')
def refresh_profile(worker,p:str=None):
    profileService = Get(ProfileService)
    if p==None:
        return {'message':f'No Profile queue was given'}
    hostname = [worker.hostname]
    print('Mocking profile update')
    worker.app.control.add_consumer(queue=p,reply=True,destination=hostname)
    return {'message':'Sucessfully refresh the profile'}

@control_command(args=[('w', str)],signature='[W=None]')
def refresh_workflow(worker,w:str=None):
    workflowService = Get(WorkflowService)
    if w==None:
        return {'message':f'No workflow was given'}
    hostname = [worker.hostname]
    print('Mocking profile update')
    for p in []:
        worker.app.control.add_consumer(queue=p,reply=True,destination=hostname)
    return {'message':'Sucessfully refresh workflow'}


@control_command(args=[('w', str)],signature='[W=None]')
def refresh_agentic(worker,a:str=None):
    remoteAgentService = Get(RemoteAgentService)
    """queue are per profile provide, so each agent is binded to a llm profile provider, so needs to stop all queues related to the llm profile provider and/or refresh the remote agent service mini services"""
    if a==None:
        # TODO stop all agentic queues and refresh the remote agents service
        return {'message':f'No workflow was given'}
    hostname = [worker.hostname]

    print('Mocking agentic update')
    for p in []:
        worker.app.control.add_consumer(queue=p,reply=True,destination=hostname)
    return {'message':'Sucessfully refresh workflow'}


#============================================================================================================#

@RegisterTask(TaskHeaviness.HEAVY)
def task_ghost_call(*args,**kwargs):
    return "ghosts called"

#============================================================================================================#

if CAPABILITIES['email']:

    if CAPABILITIES['object']:
        @RegisterTask(TaskHeaviness.MODERATE)
        def task_send_template_mail(*args,**kwargs):
            workflowService = Get(WorkflowService)
            emailService: EmailSenderService = Get(EmailSenderService),
            email_profile = kwargs.get('email_profile',None)
            emailMiniService=emailService.MiniServiceStore.get(email_profile)
            return emailMiniService.sendTemplateEmail(*args,**kwargs)

        @RegisterTask(TaskHeaviness.MODERATE)
        def task_send_custom_mail(*args,**kwargs):
            workflowService = Get(WorkflowService)
            emailService: EmailSenderService = Get(EmailSenderService)
            email_profile = kwargs.get('email_profile',None)
            emailMiniService=emailService.MiniServiceStore.get(email_profile)
            return emailMiniService.sendCustomEmail(*args,**kwargs)
    
    def task_send_simple_mail(*args,**kwargs):
        ...

#============================================================================================================#

if CAPABILITIES['twilio']:
    @RegisterTask(TaskHeaviness.LIGHT)
    def task_send_custom_sms(*args,**kwargs):
        workflowService = Get(WorkflowService)
        smsService:SMSService = Get(SMSService)
        return smsService.send_custom_sms(*args,**kwargs)

    if CAPABILITIES['object']:
        @RegisterTask(TaskHeaviness.LIGHT)
        def task_send_template_sms(*args,**kwargs):
            workflowService = Get(WorkflowService)
            smsService:SMSService = Get(SMSService)
            return smsService.send_template_sms(*args,**kwargs)

    #============================================================================================================#
    if CAPABILITIES['object']:
        @RegisterTask(TaskHeaviness.LIGHT)
        def task_send_template_voice_call(*args,**kwargs):
            workflowService = Get(WorkflowService)
            callService:CallService = Get(CallService)
            return callService.send_template_voice_call(*args,**kwargs)

    @RegisterTask(TaskHeaviness.LIGHT)
    def task_send_twiml_voice_call(*args,**kwargs):
        workflowService = Get(WorkflowService)
        callService:CallService = Get(CallService)
        return callService.send_twiml_voice_call(*args,**kwargs)
        
    @RegisterTask(TaskHeaviness.LIGHT)
    def task_send_custom_voice_call(*args,**kwargs):
        workflowService = Get(WorkflowService)
        callService:CallService = Get(CallService)
        return callService.send_custom_voice_call(*args,**kwargs)

#============================================================================================================#

if CAPABILITIES['webhook']:
    @RegisterTask(TaskHeaviness.VERY_LIGHT)
    def task_send_webhook(*args,**kwargs):
        workflowService = Get(WorkflowService)
        webhookService:WebhookService = Get(WebhookService)
        webhook_profile = kwargs.get('webhook_profile',None)
        webhookMiniService=webhookService.MiniServiceStore.get(webhook_profile)
        return webhookMiniService.deliver(*args,**kwargs)

##############################################           ##################################################

if CAPABILITIES['agentic']:

    @RegisterTask(TaskHeaviness.HEAVY)
    def task_prompt_agentic(*args,**kwargs):
        workflowService = Get(WorkflowService)
        remoteAgentService = Get(RemoteAgentService)
        remoteAgent = kwargs.get('agent',None)
        remoteAgentMiniService=remoteAgentService.MiniServiceStore.get(remoteAgent)
        return remoteAgentMiniService.Prompt(*args,**kwargs)


if CAPABILITIES['notification']:
    ...


if CAPABILITIES['message']:
    ...