"""
Module to easily manage retrieving user information from the request object.
"""

from fastapi import Request
from fastapi.security import APIKeyHeader

API_KEY_HEADER = 'X-API-KEY'

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
        return request.headers.get(API_KEY_HEADER)
    return APIKeyHeader(name=API_KEY_HEADER)