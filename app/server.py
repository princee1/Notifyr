"""
Contains the FastAPI app
"""

from starlette.types import ASGIApp
from services.security_service import SecurityService
from definition._ressource import Ressource
from container import InjectInMethod
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction
from typing import Any, Awaitable, Callable, MutableMapping
import time
from interface.middleware import InjectableMiddlewareInterface


class ProcessTimeMiddleWare(BaseHTTPMiddleware):

    def __init__(self, app, dispatch=None) -> None:
        super().__init__(self, app, dispatch)

    async def dispatch(self, request: Request, call_next: Callable[..., Response]):
        start_time = time.time()
        response: Response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response


class SecurityMiddleWare(BaseHTTPMiddleware, InjectableMiddlewareInterface):

    def __init__(self, app, dispatch=None) -> None:
        BaseHTTPMiddleware.__init__(self, app, dispatch)
        InjectableMiddlewareInterface.__init__(self)

    async def dispatch(self, request: Request, call_next: Callable[..., Response]):
        pass

    @InjectInMethod
    def inject_middleware(self, securityService: SecurityService):
        self.securityService = securityService
        return super().inject_middleware()


class FastAPIServer():

    def __init__(self, ressources: list[type[Ressource]], middlewares: list[type[BaseHTTPMiddleware]]) -> None:
        self.ressources = ressources
        self.middlewares = middlewares
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def buildRessources(self):
        pass

    pass
