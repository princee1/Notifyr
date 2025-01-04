"""
Contains the FastAPI app
"""

from dataclasses import dataclass
from container import InjectInMethod, Get, Need
from ressources import *
from starlette.types import ASGIApp
from services.config_service import ConfigService
from services.security_service import JWTAuthService, SecurityService
from utils.prettyprint import printJSON, show, PrettyPrinter_
from fastapi import Request, Response, FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction
from typing import Any, Awaitable, Callable, Dict, Literal, MutableMapping, overload,TypedDict
from interface.injectable_middleware import  InjectableMiddlewareInterface
import uvicorn
import multiprocessing
import threading
import sys
from .middleware import MIDDLEWARE
from definition._ressource import RESSOURCES, Ressource
from utils.question import ListInputHandler, ask_question, SimpleInputHandler, NumberInputHandler, ConfirmInputHandler, CheckboxInputHandler, ExpandInputHandler,exactly_one,one_or_more,one_or_more_invalid_message,instruction
from interface.events import EventInterface


AppParameterKey = Literal['title', 'summary', 'description',
                          'ressources', 'middlewares', 'port', 'log_level', 'log_config']


@dataclass
class AppParameter:
    title: str
    summary: str
    description: str
    ressources: list[type[Ressource]]
    middlewares: list[type[BaseHTTPMiddleware]]
    port: int = 8000
    log_level: str = 'debug'
    log_config: Any = None

    def __init__(self, title: str, summary: str, description: str, ressources: list[type[Ressource]], middlewares: list[type[BaseHTTPMiddleware]] = [], port=8000, log_level='debug',):
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
                      for ressource in json['ressources']]
        middlewares = [MIDDLEWARE[middleware]
                       for middleware in json['middlewares']]
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


ressources_key: set = set(RESSOURCES.keys())
middlewares_key = list(MIDDLEWARE.keys())

app_titles = []
available_ports = []

def existing_port(port): return port not in available_ports


def existing_title(title): return title not in app_titles



def createApps() -> list[AppParameter]:

    _results = []

    apps_counts = ask_question([NumberInputHandler('Enter the number of applications: ',
                               name='apps_counts', default=1, min_allowed=1, max_allowed=1)])['apps_counts']
    show(1)
    PrettyPrinter_.info(f'Creating {apps_counts} applications')
    print()
    for i in range(int(apps_counts)):

        result = ask_question([SimpleInputHandler(f'Enter the title of application {i+1} : ', name='title', default='', validate=existing_title, invalid_message='Title already exists'),
                               SimpleInputHandler(
            f'Enter the summary of application {i+1} : ', name='summary', default=''),
            SimpleInputHandler(
            f'Enter the description of application {i+1} : ', name='description', default=''),
            CheckboxInputHandler(
            f'Select the ressources of application {i+1} that will be used once per application: ', choices=ressources_key, name='ressources', validate=one_or_more, invalid_message=one_or_more_invalid_message, instruction=instruction
        ),
            CheckboxInputHandler(
            f'Select the middlewares of application {i+1} : ', choices=middlewares_key, name='middlewares', validate=one_or_more, invalid_message=one_or_more_invalid_message, instruction=instruction),
            NumberInputHandler(
            f'Enter the port of application {i+1} : ', name='port', default=8080, min_allowed=4000, max_allowed=65535),
            SimpleInputHandler(
            f'Enter the log level of application {i+1} : ', name='log_level', default='debug'),
        ],)
        ressources_key.difference_update(result['ressources'])
        result['port'] = int(result['port'])
        _results.append(AppParameter.fromJSON(result, RESSOURCES, MIDDLEWARE))
        show(1)
        printJSON(_results)

    return _results


def editApps(json_file_app_data: list[dict]) -> list[AppParameter]:
    
    titles = [json_file_app_data[i]['title']
              for i in range(len(json_file_app_data))]
    app_titles.clear()
    app_titles.extend(titles)
    available_ports.clear()
    available_ports.extend([json_file_app_data[i]['port']
                            for i in range(len(json_file_app_data))])

    show(1)
    PrettyPrinter_.info('Editing Applications')
    print()
    selected_title = ask_question([ListInputHandler('Select the application to edit: ', default=titles[0],choices=titles, name='selected_app',
                                  validate=exactly_one, invalid_message='Should be exactly one selection', instruction=instruction)])['selected_app']
    index = titles.index(selected_title)
    title = titles[index]
    show(1, f'Editing {title}')
    print()
    result = ask_question([SimpleInputHandler(f'Enter the title of application {index+1} : ', name='title', default=title, validate=existing_title, invalid_message='Title already exists'),
                           SimpleInputHandler(
        f'Enter the summary of application {index+1} : ', name='summary', default=json_file_app_data[index]['summary']),
        SimpleInputHandler(
        f'Enter the description of application {index+1} : ', name='description', default=json_file_app_data[index]['description']),
        CheckboxInputHandler(
        f'Select the ressources of application {index+1} that will be used once per application: ', choices=ressources_key, name='ressources', validate=one_or_more, invalid_message=one_or_more_invalid_message, instruction=instruction
    ),
        CheckboxInputHandler(
        f'Select the middlewares of application {index+1} : ', choices=middlewares_key, name='middlewares', validate=one_or_more, invalid_message=one_or_more_invalid_message, instruction=instruction),
        NumberInputHandler(
        f'Enter the port of application {index+1} : ', name='port', default=json_file_app_data[index]['port'], min_allowed=4000, max_allowed=65535),
        SimpleInputHandler(
        f'Enter the log level of application {index+1} : ', name='log_level', default=json_file_app_data[index]['log_level']),
    ],)
    result['port'] = int(result['port'])
    json_file_app_data[index] = result
    return [AppParameter.fromJSON(data) for data in json_file_app_data]


def start_applications(applications:list[AppParameter]):
    for app in applications:
        Application(appParameter=app).start()