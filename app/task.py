from celery import Celery
from app.container import Get, build_container
from app.services.email_service import EmailSenderService


build_container(True)

celery_app = Celery('celery_app',
                backend='redis://localhost/0',
                broker='redis://localhost/0'
            )
celery_app.conf.update(task_serializer='pickle', accept_content=['pickle'])
celery_app.autodiscover_tasks(['app.services'], related_name='celery_service')


@celery_app.task
def task_send_email():
    ...

