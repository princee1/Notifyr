from celery import Celery

celery_app = Celery('celery_app',
                backend='redis://localhost/0',
                broker='redis://localhost/0'
            )
celery_app.conf.update(task_serializer='pickle', accept_content=['pickle'])
celery_app.autodiscover_tasks(['app.services'], related_name='celery_service')


# app.conf.update(
#                 task_serializer="json",
#                 result_serializer="json",
#                 accept_content=["json"],
#                 timezone="UTC",
#                 enable_utc=True
#             )