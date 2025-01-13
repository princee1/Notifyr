"""
Contains the FastAPI app
"""

from dataclasses import dataclass
from container import InjectInMethod, Get, Need
from ressources import *
from starlette.types import ASGIApp
from services.config_service import ConfigService
from services.security_service import JWTAuthService, SecurityService
from fastapi import Request, Response, FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction
from typing import Any, Awaitable, Callable, Dict, Literal, MutableMapping, overload,TypedDict
import uvicorn
import multiprocessing
import threading
import sys
from definition._ressource import RESSOURCES, BaseRessource
from interface.events import EventInterface


AppParameterKey = Literal['title', 'summary', 'description',
                          'ressources', 'middlewares', 'port', 'log_level', 'log_config']


@dataclass
class AppParameter:
    title: str
    summary: str
    description: str
    ressources: list[type[BaseRessource]]
    middlewares: list[type[BaseHTTPMiddleware]]
    port: int = 8000
    log_level: str = 'debug'
    log_config: Any = None

    def __init__(self, title: str, summary: str, description: str, ressources: list[type[BaseRessource]], middlewares: list[type[BaseHTTPMiddleware]] = [], port=8000, log_level='debug',):
        self.title: str = title
        self.summary: str = summary
        self.description: str = description
        self.ressources = ressources
        self.middlewares = middlewares
        self.port = port
        self.log_level = log_level

    def toJSON(self) -> Dict[AppParameterKey, Any]:
        return {
            'title': self.title,
            'summary': self.summary,
            'description': self.description,
            'ressources': [ressource.__name__ for ressource in self.ressources],
            'middlewares': [middleware.__name__ for middleware in self.middlewares],
            'port': self.port,
            'log_level': self.log_level,
        }

    def set_fromJSON(self, json: Dict[AppParameterKey, Any], RESSOURCES, MIDDLEWARE):
        clone = AppParameter.fromJSON(json, RESSOURCES, MIDDLEWARE)
        self.__dict__ = clone.__dict__
        return self

    @staticmethod
    def fromJSON(json: Dict[AppParameterKey, Any], RESSOURCES, MIDDLEWARE):
        title = json['title']
        summary = json['summary']
        description = json['description']
        ressources = [RESSOURCES[ressource]
                      for ressource in json['ressources'] if ressource in RESSOURCES]
        middlewares = [MIDDLEWARE[middleware]
                       for middleware in json['middlewares'] if middleware in MIDDLEWARE]
        port = json['port']
        slog_level = json['log_level']
        return AppParameter(title, summary, description, ressources, middlewares, port, slog_level,)


class Application(EventInterface):

    def __init__(self,appParameter:AppParameter): # TODO if it important add other on_start_up and on_shutdown hooks

        self.thread = threading.Thread(
            None, self.run, appParameter.title, daemon=False)
        self.log_level = appParameter.log_level
        self.log_config = appParameter.log_config
        self.port = appParameter.port
        self.ressources = appParameter.ressources
        self.middlewares = appParameter.middlewares
        self.configService  = Get(ConfigService)
        self.app = FastAPI(title=appParameter.title, summary=appParameter.summary, description=appParameter.description,
                           on_shutdown=[self.on_shutdown], on_startup=[self.on_startup])
        self.add_middlewares()
        self.add_ressources()
        pass

    def start(self):
        #self.thread.start()
        self.run()

    def start_server(self):
        uvicorn.run(self.app, port=self.port, loop="asyncio")

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
        jwtService = Get(JWTAuthService)
        jwtService.set_generation_id(False)

    def on_shutdown(self):
        pass

    pass

#######################################################                          #####################################################
