from functools import wraps
from typing import Type,Callable
from fastapi import HTTPException, Request, Response
from app.container import Get
from app.definition._service import BaseService
from app.errors.service_error import ServiceMajorSystemFailureError, ServiceNotAvailableError, ServiceTemporaryNotAvailableError


def service_lock_decorator(service:Type[BaseService]):
    def decorator(func:Callable):
        @wraps(func)
        async def wrapper(request:Request,response:Response,*args,**kwargs):
            s = Get(service)
            async with s.statusLock.reader:
                try:
                    s.check_status()
                except ServiceMajorSystemFailureError as e:
                    raise HTTPException(
                        
                    )
                except ServiceNotAvailableError as e: 
                    raise HTTPException(

                    )
                except ServiceTemporaryNotAvailableError as e:
                    raise HTTPException(

                    )
                return await func(*args,*kwargs)
        return wrapper
    return decorator