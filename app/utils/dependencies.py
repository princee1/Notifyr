"""
Module to easily manage retrieving user information from the request object.
"""

from typing import Annotated, Any, Callable, Type, TypeVar, Literal
from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials,HTTPBearer
from .constant import HTTPHeaderConstant

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

def GetDependency(kwargs:dict[str,Any],key:str|None = None,cls:type|None = None):
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

def get_client_ip(request: Request) -> str:
    return request.client.host

def get_api_key(request: Request=None) -> str:
    if request:
        return request.headers.get(HTTPHeaderConstant.API_KEY_HEADER)
    return APIKeyHeader(name=HTTPHeaderConstant.API_KEY_HEADER)

def get_bearer_token(credentials: Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())]) -> str:
    # if isinstance(credentials,Request):
    #     return credentials.headers['Authorization'].replace('Bearer ','')
    return credentials.credentials

def get_bearer_token_from_request(request:Request):
     return request.headers['Authorization'].replace('Bearer ','')

def get_admin_token(request: Request = None):
    if request:
        return request.headers.get(HTTPHeaderConstant.ADMIN_KEY)
    return APIKeyHeader(name=HTTPHeaderConstant.ADMIN_KEY)

async def get_auth_permission(request: Request):
    if not hasattr(request.state, "authPermission") or request.state.authPermission is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return request.state.authPermission


def get_session_id(request: Request):
    ...

