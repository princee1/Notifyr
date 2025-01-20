from celery import Celery

from container import Get

#from .services.email_service import EmailSenderService
celery = Celery('celery',
                backend='redis://localhost/0',
                broker='redis://localhost/0'
            )
celery.conf.update(task_serializer='pickle', accept_content=['pickle'])
celery.autodiscover_tasks(related_name='email_ressource')

@celery.task()
def send_custom_email(content, meta, images, attachment):
    print('pk')

# app.conf.update(
#                 task_serializer="json",
#                 result_serializer="json",
#                 accept_content=["json"],
#                 timezone="UTC",
#                 enable_utc=True
#             )