"""
Contains the FastAPI app
"""
from dataclasses import dataclass
from app.container import Get
from app.ressources import *
from app.utils.prettyprint import PrettyPrinter_
from starlette.types import ASGIApp
from app.services.config_service import ConfigService
from app.services.security_service import JWTAuthService, SecurityService
from fastapi import Request, Response, FastAPI
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction
from typing import Any, Awaitable, Callable, Dict, Literal, MutableMapping, overload, TypedDict
import uvicorn
from slowapi.errors import RateLimitExceeded
from slowapi import Limiter, _rate_limit_exceeded_handler
import multiprocessing
import threading
import sys
import datetime as dt
from app.definition._ressource import RESSOURCES, BaseHTTPRessource, GlobalLimiter
from app.interface.events import EventInterface
from tortoise.contrib.fastapi import register_tortoise
import ngrok


AppParameterKey = Literal['title', 'summary', 'description',
                          'ressources', 'middlewares', 'port', 'log_level', 'log_config']

HTTPMode = Literal['HTTPS', 'HTTP']


@dataclass
class AppParameter:
    title: str
    summary: str
    description: str
    ressources: list[type[BaseHTTPRessource]]
    middlewares: list[type[BaseHTTPMiddleware]]
    port: int = 8000
    log_level: str = 'debug'
    log_config: Any = None

    def __init__(self, title: str, summary: str, description: str, ressources: list[type[BaseHTTPRessource]], middlewares: list[type[BaseHTTPMiddleware]] = [], port=8000, log_level='debug',):
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

    # TODO if it important add other on_start_up and on_shutdown hooks
    def __init__(self, appParameter: AppParameter):
        self.pretty_printer = PrettyPrinter_
        # self.thread = threading.Thread(None, self.run, appParameter.title, daemon=False)
        self.appParameter = appParameter
        self.configService: ConfigService = Get(ConfigService)
        self.app = FastAPI(title=appParameter.title, summary=appParameter.summary, description=appParameter.description,
                           on_shutdown=[self.on_shutdown], on_startup=[self.on_startup])
        self.app.state.limiter = GlobalLimiter
        self.register_tortoise()
        self.add_exception_handlers()
        self.add_middlewares()
        self.add_ressources()
        self.set_httpMode()

    def add_exception_handlers(self):
        self.app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

        @self.app.exception_handler(TypeError)
        async def type_error(request, e:TypeError):
            print(e)
            print(e.__cause__)
            return JSONResponse({'message': 'Type Error'}, status_code=500)

        @self.app.exception_handler(AttributeError)
        async def attribute_error(request, e):
            print(e)
            print(e.__cause__)

            return JSONResponse({'message': 'Attribute Error'}, status_code=500)

        @self.app.exception_handler(OSError)
        async def os_error(request, e):
            return JSONResponse({'message': 'OS Error'}, status_code=500)

        @self.app.exception_handler(KeyError)
        async def key_error(request, e):
            print(e)
            return JSONResponse({'message': 'Error while retrieving an important key '}, status_code=status.HTTP_400_BAD_REQUEST)

        @self.app.exception_handler(NotImplementedError)
        async def not_implemented_error(request, e):
            print(e)
            return JSONResponse({'message': 'The service requested is not available in this version'}, status_code=504)

        @self.app.exception_handler(MemoryError)
        async def memory_error(request, e):
            return JSONResponse({'message': 'Memory Error'}, status_code=500)

        @self.app.exception_handler(NameError)
        async def name_error(request, e):
            print(e)
            print(e.__cause__)

            return JSONResponse({'message': 'Name Error'}, status_code=500)

        @self.app.exception_handler(TimeoutError)
        async def timeout_error(request, e):
            return JSONResponse({'message': 'Timeout Error'}, status_code=500)

        @self.app.exception_handler(Exception)
        async def base_exception(request, e):
            print(e)
            print(e.__class__)
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={'message': 'An unexpected error occurred!'})

    def set_httpMode(self):
        self.mode = self.configService.HTTP_MODE
        if self.configService.HTTPS_CERTIFICATE is None or self.configService.HTTPS_KEY:
            self.mode = 'HTTP'
        return

    def start(self):
        # self.thread.start()
        self.run()

    def start_server(self):

        # match self.configService.MODE:
        #     case 'TEST':
        #         domain = self.configService.NGROK_DOMAIN
        #         ngrok_tunnel = ngrok.connect(self.appParameter.port,hostname=domain)
        #     case 'DEV':
        #         listener = ngrok.forward(f'http://localhost:{self.appParameter.port}')
        #         NGROK_URL = listener.url()
        #     case 'PROD':
        #         ...

        if self.mode == 'HTTPS':
            uvicorn.run(self.app, port=self.appParameter.port, loop="asyncio", ssl_keyfile=self.configService.HTTPS_KEY,
                        ssl_certfile=self.configService.HTTPS_CERTIFICATE)
        else:
            uvicorn.run(self.app, port=self.appParameter.port, loop="asyncio",)

    def stop_server(self):
        pass

    def run(self) -> None:
        self.start_server()

    def add_ressources(self):
        self.pretty_printer.show(
            pause_before=1, clear_stack=True, space_line=True)
        for ressource_type in self.appParameter.ressources:
            try:
                now = dt.datetime.now()
                res = ressource_type()
                self.app.include_router(
                    res.router, responses=res.default_response)
                self.pretty_printer.success(
                    f"[{now}] Ressource {ressource_type.__name__} added successfully", saveable=True)
                self.pretty_printer.wait(0.1, press_to_continue=False)
            except Exception as e:
                print(e.__class__)
                print(e)
                self.pretty_printer.error(
                    f"[{now}] Error adding ressource {ressource_type.__name__} to the app", saveable=True)
                self.pretty_printer.wait(0.1, press_to_continue=True)

        self.pretty_printer.show(
            pause_before=1, clear_stack=True, space_line=False)

    def add_middlewares(self):
        self.app.add_middleware(SlowAPIMiddleware)
        for middleware in sorted(self.appParameter.middlewares, key=lambda x: x.priority.value, reverse=True):
            self.app.add_middleware(middleware)

    def register_tortoise(self):
        pg_user = self.configService.getenv('POSTGRES_USER')
        pg_password = self.configService.getenv('POSTGRES_PASSWORD')
        pg_database = self.configService.getenv('POSTGRES_DB')
        pg_schemas = self.configService.getenv('POSTGRES_SCHEMAS', 'contacts,security')
        register_tortoise(
            app=self.app,
            db_url=f"postgres://{pg_user}:{pg_password}@localhost:5432/{pg_database}",
            modules={"models": ["app.models.contacts_model","app.models.security_model"]},
            generate_schemas=False,
            add_exception_handlers=True,    
        )

    def on_startup(self):
        jwtService = Get(JWTAuthService)
        jwtService.set_generation_id(False)

        celery_service: CeleryService = Get(CeleryService)
        celery_service.start_interval(60*60)

    def on_shutdown(self):
        # for thread in threading.enumerate():
        #     if thread is not threading.current_thread():
        #         thread.join()
        ...

#######################################################                          #####################################################
