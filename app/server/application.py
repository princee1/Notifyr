"""
Contains the FastAPI app
"""
from dataclasses import dataclass
from fastapi.responses import FileResponse, JSONResponse
from app.container import Get, CONTAINER
from app.definition._error import ServerFileError
from app.callback import Callbacks_Stream,Callbacks_Sub
from app.definition._service import ACCEPTABLE_STATES, BaseService, ServiceStatus
from app.interface.timers import IntervalInterface, SchedulerInterface
from app.ressources import *
from app.services.database_service import JSONServerDBService, MongooseService, RedisService, TortoiseConnectionService
from app.services.health_service import HealthService
from app.services.rate_limiter_service import RateLimiterService
from app.services.secret_service import HCVaultService
from app.utils.prettyprint import PrettyPrinter_
from starlette.types import ASGIApp
from app.services.config_service import ConfigService, MODE
from app.services.security_service import JWTAuthService, SecurityService
from fastapi import Request, Response, FastAPI
from slowapi.middleware import SlowAPIMiddleware
from typing import Any, Awaitable, Callable, Dict, Literal, MutableMapping, overload, TypedDict
import uvicorn
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
import datetime as dt
from app.definition._ressource import RESSOURCES, BaseHTTPRessource, ClassMetaData
from app.interface.events import EventInterface
from tortoise.contrib.fastapi import register_tortoise
import traceback
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from .app_meta import *
from .middleware import MIDDLEWARE
from app.definition._service import PROCESS_SERVICE_REPORT
from app.models.profile_model import *

HTTPMode = Literal['HTTPS', 'HTTP']

BUILTIN_ERROR = [AttributeError,NameError,TypeError,TimeoutError,BufferError,MemoryError,KeyError,NameError,IndexError,RuntimeError,OSError,Exception]

DOCUMENTS = [
                    ProfileModel,
                    SMTPProfileModel,
                    IMAPProfileModel,
                    AWSProfileModel,
                    GMailAPIProfileModel,
                    OutlookAPIProfileModel,
                    TwilioProfileModel,
                ]

_shutdown_hooks=[]
_startup_hooks=[]

def register_hook(state:Literal['shutdown','startup'],active=True):
        
    def callback(func:Callable):
        if not active:
            return func
        
        func_name = func.__name__
        
        if state == 'shutdown':
            _shutdown_hooks.append(func_name)
        else:
            _startup_hooks.append(func_name)
        return func

    return callback

class Application(EventInterface):

    # TODO if it important add other on_start_up and on_shutdown hooks
    def __init__(self,port:int=None,log_level:str=None,host:str=None):
        self.log_level = log_level
        self.host = host
        self.port =port

        self.pretty_printer = PrettyPrinter_
        self.configService: ConfigService = Get(ConfigService)
        self.rateLimiterService: RateLimiterService = Get(RateLimiterService)
        self.app = FastAPI(title=TITLE, summary=SUMMARY, description=DESCRIPTION,on_shutdown=self.shutdown_hooks, on_startup=self.startup_hooks)
        self.app.state.limiter = self.rateLimiterService.GlobalLimiter

        self.add_exception_handlers()
        self.add_middlewares()
        self.add_ressources()
        self.set_httpMode()

    def add_exception_handlers(self):
        self.app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

        def wrapper(exception:type[Exception]):

            @self.app.exception_handler(exception)
            async def callback(request,e:type[Exception]):
                print(e.__class__,e.args)
                traceback.print_exc()
                return JSONResponse({'message': 'An unexpected error occurred!'}, status_code=500)


        for e in BUILTIN_ERROR:
            wrapper(e)


        @self.app.exception_handler(ServerFileError)
        async def serve_file_error(request:Request,e:ServerFileError):
            #return StaticFiles(e.filename,html=True)
            #return HTMLResponse()
            return FileResponse(e.filename,e.status_code,e.headers)# TODO change to html_response

    def set_httpMode(self):
        self.mode = self.configService.HTTP_MODE
        if self.configService.HTTPS_CERTIFICATE is None or self.configService.HTTPS_KEY:
            self.mode = 'HTTP'
        return

    def start(self):
        if self.mode == 'HTTPS':
            uvicorn.run(self.app,host=self.host, port=self.port, loop="asyncio", ssl_keyfile=self.configService.HTTPS_KEY,
                        ssl_certfile=self.configService.HTTPS_CERTIFICATE,log_level=self.log_level)
        else:
            uvicorn.run(self.app, host=self.host, port=self.port, loop="asyncio",log_level=self.log_level)

    def stop_server(self):
        pass

    def _mount_directories(self,ress_type:type[BaseHTTPRessource]):
        meta:ClassMetaData = ress_type.meta
        for mount in meta['mount']:
            path = mount['path']
            app = mount['app']
            name = mount['name']

            self.app.mount(path,app,name)

    def add_ressources(self):
        self.pretty_printer.show(
            pause_before=1, clear_stack=True, space_line=True)
        for ressource_type in BASE_RESSOURCES:
            try:
                now = dt.datetime.now()
                res = ressource_type()
                meta:ClassMetaData = ressource_type.meta
                
                if not meta['mount_ressource']:
                    continue
                
                self.app.include_router(res.router, responses=res.default_response)
                self._mount_directories(ressource_type)
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
        
        for middleware in sorted(MIDDLEWARE.values(), key=lambda x: x.priority.value, reverse=True):
            self.app.add_middleware(middleware)
            
    @register_hook('startup')
    async def on_startup(self):

        BaseService.CONTEXT = 'async'

        redisService = Get(RedisService)
        
        if redisService.service_status == ServiceStatus.AVAILABLE:
            await redisService.create_group()
            redisService.register_consumer(callbacks_stream=Callbacks_Stream,callbacks_sub=Callbacks_Sub)

        FastAPICache.init(RedisBackend(redisService.redis_cache), prefix="fastapi-cache")

    @register_hook('shutdown',active=True)
    async def on_shutdown(self):
        redisService:RedisService = Get(RedisService)
        redisService.to_shutdown = True
        await redisService.close_connections()

    @register_hook('startup',)
    def start_tickers(self):
        taskService:TaskService =  Get(TaskService)
        taskService.start()

        vaultService: HCVaultService = Get(HCVaultService) 
        vaultService.start()

        celery_service: CeleryService = Get(CeleryService)
        celery_service.start_interval(10)

        tortoiseConnService = Get(TortoiseConnectionService)
        tortoiseConnService.start()

        mongooseService = Get(MongooseService)
        mongooseService.start()

        jsonServerService = Get(JSONServerDBService)
        jsonServerService.start()
    
    @register_hook('shutdown')
    def stop_tickers(self):

        tortoiseConnService = Get(TortoiseConnectionService)
        celery_service: CeleryService = Get(CeleryService)
        mongooseService = Get(MongooseService)
        vaultService = Get(HCVaultService)

        taskService:TaskService =  Get(TaskService)
        jsonServerService = Get(JSONServerDBService)
        

        services: list[SchedulerInterface] = [tortoiseConnService,mongooseService,vaultService,taskService,jsonServerService]

        for s in services:
            s.shutdown()
        
        celery_service.stop_interval()

    @register_hook('startup')
    async def register_tortoise(self):

        tortoiseConnService = Get(TortoiseConnectionService)
        if tortoiseConnService.service_status not in ACCEPTABLE_STATES:
            return
        
        await tortoiseConnService.init_connection()

    @register_hook('shutdown')
    async def close_tortoise(self):
        tortoiseConnService = Get(TortoiseConnectionService)
        if tortoiseConnService.service_status not in ACCEPTABLE_STATES:
            return

        await tortoiseConnService.close_connections()

    @register_hook('startup',active=False)
    def print_report_on_startup(self):
        CONTAINER.show_report()
        CONTAINER.show_dep_graph()

    @register_hook('startup')
    async def register_beanie(self):
        mongooseService: MongooseService = Get(MongooseService)
        if mongooseService.service_status not in ACCEPTABLE_STATES:
            return 
        
        mongooseService.register_document(*DOCUMENTS)
        await mongooseService.init_connection()
    
    @register_hook('shutdown')
    async def close_beanie(self):
        mongooseService: MongooseService = Get(MongooseService)
        if mongooseService.service_status not in ACCEPTABLE_STATES:
            return 
        
        mongooseService.close_connection()


    @property
    def shutdown_hooks(self):
        return [getattr(self,x) for x in _shutdown_hooks]

    @property
    def startup_hooks(self):
        return [getattr(self,x) for x in _startup_hooks]
    
#######################################################                          #####################################################
