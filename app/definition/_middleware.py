from fastapi import Request, Response
from typing import Callable


class MiddleWare:
    """
    The `MiddleWare` class in Python defines a middleware function that takes a request and a callback
    function as arguments.
    """
    def __init__(self) -> None:
        pass

    def middleware(self,request: Request, call_next: Callable[..., Response]):
        pass

    pass
