"""
Contains the FastAPI app
"""

from starlette.types import ASGIApp
from services.config_service import ConfigService
from services.security_service import SecurityService
from definition._ressource import Ressource
from container import InjectInMethod, Get, Need
from fastapi import Request, Response, FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction
from typing import Any, Awaitable, Callable, Dict, Literal, MutableMapping
import time
from interface.middleware import EventInterface, InjectableMiddlewareInterface
import uvicorn
import multiprocessing
import threading
from utils.fileIO import FDFlag, getFd
from json import JSONDecoder
import sys

AppParameterKey = Literal['title', 'summary', 'description', 'ressources', 'middlewares', 'port', 'log_level', 'log_config']

class AppParameter:
    def __init__(self, title: str, summary: str, description: str, ressources: list[type[Ressource]], middlewares: list[type[BaseHTTPMiddleware]] = [], port=8000, log_level='debug', log_config=None):
        self.title:str = title
        self.summary:str = summary
        self.description:str = description
        self.ressources = ressources
        self.middlewares = middlewares
        self.port = port
        self.log_level = log_level
        self.log_config = log_config
    
    def toJSON(self) -> Dict[AppParameterKey, Any]:
        return {
            'title': self.title,
            'summary': self.summary,
            'description': self.description,
            'ressources': [ressource.__name__ for ressource in self.ressources],
            'middlewares': [middleware.__name__ for middleware in self.middlewares],
            'port': self.port,
            'log_level': self.log_level,
            'log_config': self.log_config
        }
    
    def fromJSON(self, json:Dict[AppParameterKey,Any], RESSOURCES, MIDDLEWARE):
        self.title = json['title']
        self.summary = json['summary']
        self.description = json['description']
        self.ressources = [RESSOURCES[ressource] for ressource in json['ressources']]
        self.middlewares = [MIDDLEWARE[middleware] for middleware in json['middlewares']]
        self.port = json['port']
        self.log_level = json['log_level']
        self.log_config = json['log_config']
        return self
    


class Application(EventInterface):

    def __init__(self, appParameter: AppParameter):
        
        self.thread = threading.Thread(None, self.run, appParameter.title, daemon=False)
        self.log_level = appParameter.log_level
        self.log_config = appParameter.log_config
        self.port = appParameter.port
        self.ressources = appParameter.ressources
        self.middlewares = appParameter.middlewares
        self.configService: ConfigService = Get(ConfigService)
        self.app = FastAPI(title=appParameter.title, summary=appParameter.summary, description=appParameter.description,
                           on_shutdown=[self.on_shutdown], on_startup=[self.on_startup])
        self.add_middlewares()
        self.add_ressources()
        pass

    def start(self):
        self.thread.start()

    def start_server(self):
        # with open('output.txt', 'w') as file:
        #     # Redirect stdout to the file
        #     sys.stdout = file
        #     print("This will be written to the file.")
        uvicorn.run(self.app, port=self.port, loop="asyncio")
        print('Starting')

    def stop_server(self):
        pass

    def run(self) -> None:
        self.start_server()

    def add_ressources(self):
        for ressource_type in self.ressources:
            res = ressource_type()
            self.app.include_router(res.router, responses=res.default_response)
        pass

    def add_middlewares(self):
        for middleware in self.middlewares:

            self.app.add_middleware(middleware)

    def on_startup(self):
        pass

    def on_shutdown(self):
        pass

    pass
