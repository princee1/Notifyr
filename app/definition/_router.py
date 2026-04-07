from functools import wraps
from typing import Dict, Type,Callable
from fastapi import HTTPException, Request, Response,status
from app.container import Get
from app.definition._service import BaseService
from app.errors.service_error import ServiceMajorSystemFailureError, ServiceNotAvailableError, ServiceTemporaryNotAvailableError


def lock_service_wrapper(service:Type[BaseService]):

    def decorator(func:Callable):

        @wraps(func)
        async def wrapper(request:Request,response:Response,*args,**kwargs):
            s = Get(service)
            async with s.statusLock.reader:
                try:
                    s.check_status(...)
                except ServiceMajorSystemFailureError as e:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                except ServiceNotAvailableError as e: 
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE

                    )
                except ServiceTemporaryNotAvailableError as e:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE
                    )
                return await func(request,response,*args,*kwargs)
        return wrapper
    return decorator


class HandlerDetails:
    
    def __init__(self,status_code:int,detail:Callable[[Exception],str|None|dict]|None|str):
        self.status_code = status_code
        self.detail = detail
    
    def __call__(self, e):
        if callable(self.detail):
            detail = self.detail(e)
        elif isinstance(self.detail,str):
            detail = self.detail
        else:
            detail = str(e)
        raise HTTPException(self.status_code,detail)
        

def exception_handler(error:Dict[Type[Exception],HandlerDetails]):

    def decorator(func:Callable):

        @wraps(func)
        async def wrapper(request:Request,response:Response,*args,**kwargs):
            try:
                return await func(request,response,*args,*kwargs)

            except Exception as e:
                if isinstance(e,HTTPException):
                    raise e

                if e.__class__ not in error:
                    raise e
               
                error_details = error[e]
                error_details(e)
        
        return wrapper
    
    return decorator
