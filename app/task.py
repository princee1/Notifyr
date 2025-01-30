from celery import Celery
from app.services.config_service import ConfigService
from app.services.email_service import EmailSenderService
from app.container import Get, build_container

if __name__ == '__main__':
    build_container(True)

configService: ConfigService = Get(ConfigService)
# celery_app = Celery('celery_app',
#             backend=configService.CELERY_BACKEND_URL,
#             broker=configService.CELERY_MESSAGE_BROKER_URL
#         )
celery_app = Celery('celery_app',
                backend='redis://localhost/0',
                broker='redis://localhost/0'
            )
celery_app.conf.update(task_serializer='pickle', accept_content=['pickle'])
celery_app.autodiscover_tasks(['app.services'], related_name='celery_service')

@celery_app.task
def task_send_template_mail():
    emailService = Get(EmailSenderService)
    

@celery_app.task
def task_send_custom_mail():
    emailService = Get(EmailSenderService)


