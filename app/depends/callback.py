from app.container import Get, InjectInFunction
from app.models.email_model import EmailTrackingORM
from app.models.link_model import LinkEventORM,LinkORM,LinkSessionORM
from app.services.reactive_service import ReactiveService
from app.services.celery_service import CeleryService

def react_to_event():

    @InjectInFunction
    def wrapper(reactiveService:ReactiveService):
        ...
    
    return wrapper()

def add_tracking_data():
    ...

