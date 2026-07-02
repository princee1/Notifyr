from functools import wraps
from typing import Dict, Type,Callable
from fastapi import Depends, HTTPException, Request, Response,status
from app.container import Get
from app.definition._service import BaseService
from app.depends.dependencies import get_bearer_token
from app.errors.service_error import ServiceMajorSystemFailureError, ServiceNotAvailableError, ServiceTemporaryNotAvailableError
from app.services.agent.agent_service import AgentService
from app.utils.constant import HTTPHeaderConstant

agentService = Get(AgentService)

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
    
    def __init__(self,status_code:int,detail:Callable[[Exception],str|None|dict]|None|str=lambda e:str(e)):
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


def get_instance_id(request:Request)->str:
    if not (instance_id:=request.headers.get(HTTPHeaderConstant.X_NOTIFYR_APP_INSTANCE_ID,None)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,'Missing instance_id')
    return instance_id

def auth_depends(token: str = Depends(get_bearer_token)):
        if agentService.AgenticAPIKey != token:
            raise HTTPException(status_code=401,detail="Unauthorized")