from typing import Callable
from classes.template import TemplateBuildError, TemplateNotFoundError, TemplateValidationError
from definition._utils_decorator import Handler,HandlerDefaultException,NextHandlerException
from definition._service import ServiceNotAvailableError,MethodServiceNotAvailableError, ServiceTemporaryNotAvailableError
from fastapi import status, HTTPException

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
            
        
        except Exception as e:
            print(e)
            raise NextHandlerException
        

class TemplateHandler(Handler):

    def handle(self, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
            
        except TemplateNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail='Template not found')
        
        except TemplateBuildError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail='Cannot build template with data specified')

        except TemplateValidationError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail='Cannot validate template')
        
        except Exception as e:
            raise NextHandlerException