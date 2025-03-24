"""
Module to easily manage retrieving user information from the request object.
"""

from typing import Annotated, Any, Callable, Type, TypeVar, Literal
from fastapi import Depends, HTTPException, Request, Response,status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials,HTTPBearer
from .constant import HTTPHeaderConstant
from .helper import reverseDict
import asyncio


D = TypeVar('D',bound=type)

def APIFilterInject(func:Callable | Type):

    if type(func) == type:
        annotations = func.__init__.__annotations__.copy()
    else:
        annotations = func.__annotations__.copy()
        annotations.pop('return',None)

    def wrapper(*args,**kwargs):
        filtered_kwargs = {
            key: (annotations[key](value) if isinstance(value, (str, int, float, bool, list, dict)) and annotations[key] == Literal  else value)
            for key, value in kwargs.items()
            if key in annotations
        }
        return func(*args, **filtered_kwargs)
    return wrapper


def AsyncAPIFilterInject(func:Callable | Type):

    if type(func) == type:
        annotations = func.__init__.__annotations__.copy()
    else:
        annotations = func.__annotations__.copy()
        annotations.pop('return',None)

    async def wrapper(*args,**kwargs):
        filtered_kwargs = {
            key: (annotations[key](value) if isinstance(value, (str, int, float, bool, list, dict)) and annotations[key] == Literal  else value)
            for key, value in kwargs.items()
            if key in annotations
        }
        return await func(*args, **filtered_kwargs)
    return wrapper


def GetDependency(kwargs:dict[str,Any],key:str|None = None,cls:type|None = None):
    reversed_kwargs = reverseDict(kwargs)
    if key == None and cls == None:
        raise KeyError
    # if cls:
    #     for 
    return 

# TODO: Check if we can raise exception if some header value are not present

def get_user_language(request: Request) -> str:
    """
    Retrieve the preferred language of the user from the request object.

    This function extracts the language information from the incoming HTTP request,
    typically from the 'Accept-Language' header or any custom language parameter.

    Parameters:
    -----------
    request : Request
        The FastAPI Request object containing information about the incoming HTTP request.

    Returns:
    --------
    str
        A string representing the user's preferred language code (e.g., 'en', 'es', 'fr').
        If no language preference is found, it may return a default language or None.
    """
    return ... 

def get_user_agent(request: Request) -> str:
    return request.headers.get('User-Agent')

def get_timezone(request:Request)->str:
    ...

def get_client_ip(request: Request) -> str:
    return request.client.host

def get_response_id(r:Response = None)-> str | None:
    try:
        if r:
            return r.headers[HTTPHeaderConstant.REQUEST_ID]
        return APIKeyHeader(name=HTTPHeaderConstant.REQUEST_ID)
    except KeyError as e:
        return None



def get_api_key(request: Request=None) -> str:
    if request:
        return request.headers.get(HTTPHeaderConstant.API_KEY_HEADER)
    return APIKeyHeader(name=HTTPHeaderConstant.API_KEY_HEADER)

def get_bearer_token(credentials: Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())]) -> str:
    # if isinstance(credentials,Request):
    #     return credentials.headers['Authorization'].replace('Bearer ','')
    return credentials.credentials

def get_bearer_token_from_request(request: Request):
    try:
        return request.headers['Authorization'].replace('Bearer ', '')
    except KeyError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing")

def get_admin_token(request: Request = None):
    if request:
        return request.headers.get(HTTPHeaderConstant.ADMIN_KEY)
    return APIKeyHeader(name=HTTPHeaderConstant.ADMIN_KEY)

async def get_auth_permission(request: Request):
    if not hasattr(request.state, "authPermission") or request.state.authPermission is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return request.state.authPermission

async def get_request_id(request: Request):
    if not hasattr(request.state, "request_id") or request.state.request_id is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve request id")
    return request.state.request_id

def get_query_params(name,default=None)->Callable[[Request],str|None]:

    def depends(request:Request):
        return request.query_params.get(name,default)

    return depends


def get_contact_token():
    return APIKeyHeader(name=HTTPHeaderConstant.CONTACT_TOKEN)

def get_session_id(request: Request):
    ...

def get_router_name(request: Request):
    ...