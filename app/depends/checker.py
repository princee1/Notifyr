from app.classes.celery import SchedulerModel

def check_celery_service(scheduler:SchedulerModel):
    return scheduler.task_type =='now'
        
    