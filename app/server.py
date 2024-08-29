"""
Contains the FastAPI app
"""

from services.security_service import SecurityService
from definition._ressource import Ressource
from definition._middleware import MiddleWare
from container import InjectInConstructor
from fastapi import  Request, Response
from typing import Callable
import time


class ProcessTimeMiddleWare(MiddleWare):

    async def middleware(self,request: Request, call_next: Callable[..., Response]):
        start_time = time.time()
        response: Response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

class SecurityMiddleWare(MiddleWare):

    @InjectInConstructor
    def __init__(self,securityService:SecurityService) -> None:
        super().__init__()
        self.securityService:SecurityService = securityService

    def middleware(self,request: Request, call_next: Callable[..., Response]):
        pass

class FastAPIServer():
    
    def __init__(self,ressources:list[type[Ressource]],middlewares:list[type[MiddleWare]]) -> None:
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