from fastapi import Request

def get_user_language(request: Request) -> str:
    return ... 

def get_user_agent(request: Request) -> str:
    return ...
