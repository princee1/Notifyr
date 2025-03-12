from typing import Callable
from app.classes.auth_permission import WSPathNotFoundError
from app.classes.template import TemplateBuildError, TemplateNotFoundError, TemplateValidationError
from app.definition._error import BaseError
from app.definition._utils_decorator import Handler,HandlerDefaultException,NextHandlerException
from app.definition._service import MethodServiceNotExistsError, ServiceNotAvailableError,MethodServiceNotAvailableError, ServiceTemporaryNotAvailableError
from fastapi import status, HTTPException
from app.classes.celery import CelerySchedulerOptionError, CeleryTaskNameNotExistsError,CeleryTaskNotFoundError
from celery.exceptions import AlreadyRegistered,MaxRetriesExceededError,BackendStoreError,QueueNotFound,NotRegistered

from app.models.contacts_model import ContactAlreadyExistsError, ContactNotExistsError
from app.services.assets_service import AssetNotFoundError
from twilio.base.exceptions import TwilioRestException

from tortoise.exceptions import OperationalError,DBConnectionError,ValidationError
class ServiceAvailabilityHandler(Handler):
    
    async def handle(self, function:Callable, *args, **kwargs):
        try:
            return await function(*args, **kwargs)
        
        except ServiceNotAvailableError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,detail='Service not available')
            
        except MethodServiceNotAvailableError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,detail='Method service not available')

        except MethodServiceNotExistsError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail='Method service does not exists')


        except ServiceTemporaryNotAvailableError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,detail='Service temporary not available')
                  
        
class TemplateHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)

        except AssetNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail='Asset not found')
        
        except TemplateNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail='Template not found')
        
        except TemplateBuildError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail='Cannot build template with data specified')

        except TemplateValidationError as e:
            error = e.args[0]
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail={
                'details':error,
                'message': 'Validation Error'
            })
        
class WebSocketHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
           return await function(*args, **kwargs)
        
        except WSPathNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail={
                'message':'WS Path Not Found'
            })


class CeleryTaskHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
           return await function(*args,**kwargs)
        
        except CeleryTaskNotFoundError as e:
           raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail={})

        except CeleryTaskNameNotExistsError as e:
           raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail={})

        except CelerySchedulerOptionError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail={})
        
        except QueueNotFound as e:
           raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail={})
            
        except AlreadyRegistered as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail={})

        except NotRegistered as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail={})
            
        except MaxRetriesExceededError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail={})
        
class TwilioHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)
    
        except TwilioRestException as e:
            raise HTTPException(status=status.HTTP_400_BAD_REQUEST,details={})
    


class ContactsHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:

            return await function(*args, **kwargs)
        
        except ContactNotExistsError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail={'message':'The user specified does not exists',})

        except ContactAlreadyExistsError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail={'message':'Error could not create the user because info are already used','detail':e.message})
            
    
class TortoiseHandler(Handler):

    async def handle(self, function, *args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except OperationalError:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail={'message':'Database execution error',})

        except ValidationError as e:
            mess= e.args[0]
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail={'message':'Database execution error','detail':mess})

