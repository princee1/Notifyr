from typing import Callable
from app.classes.auth_permission import WSPathNotFoundError
from app.classes.template import TemplateBuildError, TemplateNotFoundError, TemplateValidationError
from app.definition._error import BaseError
from app.definition._utils_decorator import Handler,HandlerDefaultException,NextHandlerException
from app.definition._service import ServiceNotAvailableError,MethodServiceNotAvailableError, ServiceTemporaryNotAvailableError
from fastapi import status, HTTPException
from app.classes.celery import CeleryTaskNameNotExistsError,CeleryTaskNotFoundError


class ServiceAvailabilityHandler(Handler):
    
    def handle(self, function:Callable, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        
        except ServiceNotAvailableError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,detail='Service not available')
            
        except MethodServiceNotAvailableError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,detail='Method service not available')

        except ServiceTemporaryNotAvailableError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,detail='Service temporary not available')
                  
        
class TemplateHandler(Handler):

    def handle(self, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
            
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

    def handle(self, function, *args, **kwargs):
        try:
           return function(*args, **kwargs)
        
        except WSPathNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail={
                'message':'WS Path Not Found'
            })


class CeleryTaskHandler(Handler):

    def handle(self, function, *args, **kwargs):
        try:
           return function(*args,**kwargs)
        except CeleryTaskNotFoundError:
           raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail={})

        except CeleryTaskNameNotExistsError:
           raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail={})
            
