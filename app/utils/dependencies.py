"""
Module to easily manage retrieving user information from the request object.
"""

from typing import Annotated, Any, Callable
from fastapi import Depends, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials,HTTPBearer
from utils.constant import HTTPHeaderConstant


def APIFilterInject(func:Callable):

    annotations = func.__annotations__.copy()
    annotations.pop('return',None)

    def wrapper(*args,**kwargs):
        filtered_kwargs = {
            key: (annotations[key](value) if key in annotations and isinstance(value, (str, int, float, bool, list, dict)) else value)
            for key, value in kwargs.items()
            if key in annotations
        }
        return func(*args, **filtered_kwargs)
    return wrapper

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

def get_api_key(request: Any=None) -> str:
    if request:
        return request.headers.get(HTTPHeaderConstant.API_KEY_HEADER)
    return APIKeyHeader(name=HTTPHeaderConstant.API_KEY_HEADER)

def get_bearer_token(credentials: Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())]) -> str:
    return credentials.credentials

def get_admin_token(request: Any = None):
    if request:
        return request.headers.get(HTTPHeaderConstant.ADMIN_KEY)
    return APIKeyHeader(name=HTTPHeaderConstant.ADMIN_KEY)