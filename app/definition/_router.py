import asyncio
from functools import wraps
from typing import Dict, Type,Callable,overload
from fastapi import Depends, HTTPException, Request, Response,status
from app.container import Get
from app.definition._service import BaseMiniServiceManager, BaseService
from app.depends.dependencies import get_bearer_token
from app.errors.service_error import ServiceMajorSystemFailureError, ServiceNotAvailableError, ServiceTemporaryNotAvailableError
from app.services.agent.agent_service import AgentService
from app.utils.constant import HTTPHeaderConstant

# Import exception types for the handler mapping
from app.definition._service import (
    ServiceNotImplementedError, MethodServiceNotImplementedError,
    MethodServiceNotExistsError, StateProtocolMalFormattedError,
    ServiceDoesNotExistError, MethodServiceNotAvailableError
)
from app.errors.service_error import (
    MiniServiceAlreadyExistsError, MiniServiceDoesNotExistsError,
    MiniServiceCannotBeIdentifiedError
)



def service_temporary_not_available_detail(e: ServiceTemporaryNotAvailableError) -> dict:
    """Extract detail from ServiceTemporaryNotAvailableError"""
    return {
        'service': getattr(e, 'service', 'Unknown'),
        'message': 'Service temporary not available'
    }

class HandlerDetails:
    
    @overload
    def __init__(self,status_code:int,detail:Callable[[Exception],str|None|dict]|None|str=lambda e:str(e)):
        ...

    @overload
    def __init__(self,error:HTTPException):
        ...
    
    def __init__(self,*args,**kwds):
        if len(kwds)>=1:
            self.status_code = args[0]
            self.detail = kwds['detail']
            self.error = None
        elif len(args)==2:
            self.status_code = args[0]
            self.detail = args[1]
            self.error = None
        elif len(args)==1:
            self.error = args[0]
    
    def __call__(self, e):
        if callable(self.detail):
            detail = self.detail(e)
        elif isinstance(self.detail,str):
            detail = self.detail
        else:
            detail = str(e)
        raise HTTPException(self.status_code,detail)
        

SERVICE_HANDLER_DETAILS: Dict[Type[Exception], 'HandlerDetails'] = {
    # ServiceAvailabilityHandler exceptions
    ServiceNotAvailableError: HandlerDetails(status.HTTP_500_INTERNAL_SERVER_ERROR, 'Service not available'),
    MethodServiceNotAvailableError: HandlerDetails(status.HTTP_500_INTERNAL_SERVER_ERROR, 'Method service not available'),
    MethodServiceNotExistsError: HandlerDetails(status.HTTP_500_INTERNAL_SERVER_ERROR, 'Method service does not exist'),
    ServiceTemporaryNotAvailableError: HandlerDetails(status.HTTP_503_SERVICE_UNAVAILABLE, service_temporary_not_available_detail),
    ServiceNotImplementedError: HandlerDetails(status.HTTP_501_NOT_IMPLEMENTED, 'Service not implemented'),
    MethodServiceNotImplementedError: HandlerDetails(status.HTTP_501_NOT_IMPLEMENTED, 'Method Service not implemented'),
    StateProtocolMalFormattedError: HandlerDetails(status.HTTP_500_INTERNAL_SERVER_ERROR, 'State Protocol MalFormatted'),
    ServiceDoesNotExistError: HandlerDetails(status.HTTP_500_INTERNAL_SERVER_ERROR, 'Service does not exist'),
}

MINI_SERVICE_HANDLER_DETAILS: Dict[Type[Exception], 'HandlerDetails'] = {
    # MiniServiceHandler exceptions
    MiniServiceAlreadyExistsError: HandlerDetails(status.HTTP_409_CONFLICT, 'MiniService already exists'),
    MiniServiceDoesNotExistsError: HandlerDetails(status.HTTP_404_NOT_FOUND, 'MiniService does not exist'),
    MiniServiceCannotBeIdentifiedError: HandlerDetails(status.HTTP_400_BAD_REQUEST, 'MiniService cannot be identified'),
}


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

def service_yielder(s_cls:Type[BaseMiniServiceManager],ping:bool=False,m:str=None):
    s = Get(s_cls)
    async def decorator(service:str):
        async with s.lock('reader',service,'reader') as mini:
            if ping:
                await s.pingService(True,None,service,True)
            if m != None and (method:=getattr(mini,m,None)) and callable(method):
                if asyncio.iscoroutinefunction(method):
                    await method(True)
                else:
                    method(True)
            yield mini
    
    return decorator

def exception_handler(error:Dict[Type[Exception],HandlerDetails]|None):
    """
    Decorator for exception handling with automatic HTTP response mapping.
    
    Args:
        error: Optional dictionary mapping exception types to HandlerDetails.
               If None, uses the global EXCEPTION_HANDLER_MAPPING.
               Can be customized or extended for specific handlers.
    """
    
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
               
                error_details = error[e.__class__]
                error_details(e)
        
        return wrapper
    
    return decorator

def get_instance_id(request:Request)->str:
    if not (instance_id:=request.headers.get(HTTPHeaderConstant.X_NOTIFYR_APP_INSTANCE_ID,None)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,'Missing instance_id')
    return instance_id

def auth_depends(token: str = Depends(get_bearer_token)):
    agentService = Get(AgentService)
    if agentService.AgenticAPIKey != token:
        raise HTTPException(status_code=401,detail="Unauthorized")