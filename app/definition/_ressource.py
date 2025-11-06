"""
The `BaseResource` class initializes with a `container` attribute assigned from the `CONTAINER`
instance imported from `container`.
"""
from inspect import isclass
from types import NoneType
from typing import Any, Callable, Dict, Iterable, List, Literal, Mapping, Optional, Sequence, TypeVar, Type, TypedDict

from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from app.classes.profiles import ProfileNotSpecifiedError, ProfileTypeNotMatchRequest
from app.definition._cost import bind_cost_request
from app.definition._ws import W
from app.services.config_service import MODE, ConfigService
from app.utils.helper import copy_response, issubclass_of
from app.utils.constant import SpecialKeyParameterConstant
from app.services import AssetService, CostService
from app.container import Get, Need
from app.definition._service import S, BaseMiniService, BaseMiniServiceManager, BaseService
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from app.utils.prettyprint import PrettyPrinter_, PrettyPrinter
import functools
from fastapi import BackgroundTasks
from app.interface.events import EventInterface
from enum import Enum
from ._utils_decorator import *
from app.classes.auth_permission import FuncMetaData, Role, WSPathNotFoundError
import asyncio
from asgiref.sync import sync_to_async
import warnings
from app.depends.variables import SECURITY_FLAG



configService: ConfigService = Get(ConfigService)
costService:CostService = Get(CostService)

RequestLimit = 0


PING_SERVICE_TOUCH = 0.25
STATUS_LOCK_TOUCH = 0.50
PATH_SEPARATOR = "/"


MIN_TIMEOUT = -1



class MountMetaData(TypedDict):
    app: StaticFiles
    name: str
    path: str


class ClassMetaData(TypedDict):
    prefix: str
    routers: list
    add_prefix: bool
    websockets: list[W]
    mount: List[MountMetaData]
    mount_ressource:bool
    ressource_id:str
    parent:list[Type]
    classname:str



class NoFunctionProvidedWarning(UserWarning):
    pass


RESSOURCES: dict[str, type] = {}
"""
This variable contains a direct reference to the class by the class name
"""

PROTECTED_ROUTES: dict[str, list[str]] = {}
"""
This variable contains the name of all the protected routes of the used ressources

"""

ROUTES: dict[str, list[dict]] = {}
"""
This variable contains all the routes of the used ressources
"""

DECORATOR_METADATA: dict[str, dict[str, list[tuple[Callable, float]]]] = {}
"""
This variable holds all the callback that will be decorate an http function
"""

EVENTS: dict[str, set[str]] = {}
"""
This variable contains the functions that will be an events listener
"""
################################################################                           #########################################################


class Helper:

    @staticmethod
    async def return_result(tf:Callable,a,k):
        result = tf(*a, **k)
        if asyncio.iscoroutine(result):
            return await result
        return result

    @staticmethod
    def get_class_name_from_method(func: Callable) -> str:
        return func.__qualname__.split('.')[0]

    @staticmethod
    def response_decorator(func: Callable):

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            response: Response = kwargs.get('response', None)

            if isinstance(result, Response):
                ...
            elif isinstance(result, (dict, list, set, tuple)):
                result = JSONResponse(result,)

            elif isinstance(result, (int, str, float, bool)):
                result = PlainTextResponse(str(result))

            elif result == None:
                result = JSONResponse({},)

            return copy_response(result, response)

        return wrapper

    @staticmethod
    def add_protected_route_metadata(class_name: str, operation_id: str):
        if class_name in PROTECTED_ROUTES:
            PROTECTED_ROUTES[class_name].append(operation_id)
        else:
            PROTECTED_ROUTES[class_name] = [operation_id]

    @staticmethod
    def appends_funcs_callback(func: Callable, wrapper: Callable, priority: DecoratorPriority, touch: float = 0):
        class_name = Helper.get_class_name_from_method(func)
        if class_name not in DECORATOR_METADATA:
            DECORATOR_METADATA[class_name] = {}

        if func.__name__ not in DECORATOR_METADATA[class_name]:
            DECORATOR_METADATA[class_name][func.__name__] = []

        DECORATOR_METADATA[class_name][func.__name__].append(
            (wrapper, priority.value + touch))

    @staticmethod
    def filter_type_function(functions, flag=True):
        temp_pipe_func = []

        for p in functions:
            if type(p) == type:
                p=p()
            temp_pipe_func.append(p)

        return temp_pipe_func

    @staticmethod
    def stack_decorator(decorated_function, deco_type: Type[DecoratorObj], empty_decorator: bool, default_error: dict, error_type: Type[DecoratorException]):
        def wrapper(function: Callable):

            @functools.wraps(function)
            async def callback(*args, **kwargs):  # Function that will be called
                if empty_decorator:
                    return await function(*args, **kwargs)

                def proxy(deco, f: Callable):
                    @functools.wraps(deco)
                    async def delegator(*a, **k):
                        if type(deco) == type:
                            obj: DecoratorObj = deco()
                            return await obj.do(f, *a, **k)
                        elif isinstance(deco, deco_type):
                            return await deco.do(f, *a, **k)
                        else:
                            return await deco(f, *a, **k)
                    return delegator

                deco_prime = function
                for d in reversed(decorated_function):
                    deco_prime = proxy(d, deco_prime)

                try:
                    return await deco_prime(*args, **kwargs)
                except error_type as e:

                    if e.response != None and isinstance(e.response,Response):
                        return e.response                    

                    e.raise_http_exception()

                    if default_error == None:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Could not correctly treat the error')

                    raise HTTPException(**default_error)

            return callback
        return wrapper

################################################################                           #########################################################


class HTTPMethod(Enum):
    POST = 'POST'
    GET = 'GET'
    UPDATE = 'UPDATE'
    DELETE = 'DELETE'
    PUT = 'PUT'
    PATCH = 'PATCH'
    OPTIONS = 'OPTIONS'
    HEAD = 'HEAD'

    @staticmethod
    def to_strs(methods: list[Any] | Any):
        if isinstance(methods, HTTPMethod):
            return [methods.value]
        methods: list[HTTPMethod] = methods
        return [method.value for method in methods]


class HTTPExceptionParams(TypedDict):
    status_code: int
    detail: Any | None
    headers: dict[str, str] | None = None


class RessourceResponse(TypedDict):
    message: str
    details: Optional[Any]


class HTTPRessourceMetaClass(type):
    def __new__(cls, name, bases, dct):
        # setattr(cls,'meta',{})
        return super().__new__(cls, name, bases, dct)


class BaseHTTPRessource(EventInterface, metaclass=HTTPRessourceMetaClass):

    @staticmethod
    def _build_operation_id(route_name: str, prefix: str, method_name: list[HTTPMethod] | HTTPMethod, operation_id: str) -> str:
        if operation_id != None:
            return operation_id

        m = HTTPMethod.to_strs(method_name) if isinstance(
            method_name, list) else [method_name]
        return route_name.replace(PATH_SEPARATOR, "_") + '_'.join(m)

    @staticmethod
    def HTTPRoute(path: str, methods: Iterable[HTTPMethod] | HTTPMethod = [HTTPMethod.POST], operation_id: str = None, dependencies: Sequence[Depends] = None, response_model: Any = None, response_description: str = "Successful Response",
                  responses: Dict[int | str, Dict[str, Any]] | None = None,
                  deprecated: bool | None = None, mount: bool = True):
        def decorator(func: Callable):
            computed_operation_id = BaseHTTPRessource._build_operation_id(
                path, None, methods, operation_id)

            setattr(func, 'meta', FuncMetaData())
            func.meta['operation_id'] = computed_operation_id
            func.meta['roles'] = {Role.PUBLIC}
            func.meta['excludes'] = set()
            func.meta['options'] = []
            func.meta['limit_obj'] = None
            func.meta['limit_exempt'] = False
            func.meta['shared'] = None
            func.meta['default_role'] = True

            if not mount:
                return func

            class_name = Helper.get_class_name_from_method(func)
            kwargs = {
                'path': path,
                'endpoint': func.__name__,
                'operation_id': computed_operation_id,
                'dependencies': dependencies,
                'summary': func.__doc__,
                'response_model': response_model,
                'methods': HTTPMethod.to_strs(methods),
                'response_description': response_description,
                'responses': responses,
                'deprecated': deprecated,
            }
            if class_name not in ROUTES:
                ROUTES[class_name] = []

            ROUTES[class_name].append(kwargs)

            return func
        return decorator

    @staticmethod
    def Get(path: str, operation_id: str = None, dependencies: Sequence[Depends] = None, response_model: Any = None, response_description: str = "Successful Response",
            responses: Dict[int | str, Dict[str, Any]] | None = None,
            deprecated: bool | None = None, mount: bool = True):
        return BaseHTTPRessource.HTTPRoute(path, [HTTPMethod.GET], operation_id, dependencies, response_model, response_description, responses, deprecated, mount)

    @staticmethod
    def Post(path: str, operation_id: str = None,  dependencies: Sequence[Depends] = None, response_model: Any = None, response_description: str = "Successful Response",
             responses: Dict[int | str, Dict[str, Any]] | None = None,
             deprecated: bool | None = None, mount: bool = True):
        return BaseHTTPRessource.HTTPRoute(path, [HTTPMethod.POST], operation_id, dependencies, response_model, response_description, responses, deprecated, mount)

    @staticmethod
    def Delete(path: str, operation_id: str = None, dependencies: Sequence[Depends] = None, response_model: Any = None, response_description: str = "Successful Response",
               responses: Dict[int | str, Dict[str, Any]] | None = None,
               deprecated: bool | None = None, mount: bool = True):
        return BaseHTTPRessource.HTTPRoute(path, [HTTPMethod.DELETE], operation_id, dependencies,  response_model, response_description, responses, deprecated, mount)

    @staticmethod
    def OnEvent(event: str):
        # VERIFY use reactivex?
        def decorator(func: Callable):

            if getattr(func, 'meta'):
                raise AttributeError(
                    'Cannot set an http route as an event listener')
            setattr(func, 'event', event)
            class_name = Helper.get_class_name_from_method(func)
            if class_name not in EVENTS:
                EVENTS[class_name] = set([func.__qualname__])
            else:
                EVENTS[class_name].add(func.__qualname__)

            return func

        return decorator

    def _register_event(self,):
        class_name = self.__class__.meta['classname']
        if class_name not in EVENTS:
            return
        self.events = {}
        for func in EVENTS[class_name]:
            f = getattr(self, func)
            self.events[f.event] = f

    def emits(self, event: str, data: Any):
        if event not in self.events:
            return
        return self.events[event](data)

    def _stack_callback(self):
        if self.__class__.meta['classname'] not in DECORATOR_METADATA:
            return
        M = DECORATOR_METADATA[self.__class__.meta['classname']]
        for f in M:
            if hasattr(self, f):
                stacked_callback = M[f].copy()
                c = getattr(self, f)
                if not asyncio.iscoroutinefunction(c):
                    setattr(self, f, sync_to_async(c))
                    c= getattr(self,f)
                for sc in sorted(stacked_callback, key=lambda x: x[1], reverse=True):
                    sc_ = sc[0]
                    c = sc_(c)
                setattr(self, f, c)

    def _set_rate_limit(self):
        for end in ROUTES[self.__class__.meta['classname']]:
            func_name = end['endpoint']
            func_attr = getattr(self, func_name)
            meta: FuncMetaData = getattr(func_attr, 'meta')

            limit_obj = meta['limit_obj']
            shared = meta['shared']

            if meta['limit_exempt']:
                func_attr = costService.GlobalLimiter.exempt(func_attr)
                setattr(self, func_name, func_attr)
                return

            if limit_obj:
                if not shared:
                    func_attr = costService.GlobalLimiter.limit(**limit_obj)(func_attr)
                else:
                    func_attr = costService.GlobalLimiter.shared_limit(
                        **limit_obj)(func_attr)

                setattr(self, func_name, func_attr)

    def __init_subclass__(cls: Type) -> None:

        RESSOURCES[cls.__name__] = cls
        # ROUTES[cls.__name__] = []
        setattr(cls, 'meta', {})
        super().__init_subclass__()

    def __init__(self, dependencies=None, router_default_response: dict = None) -> None:
        self.assetService: AssetService = Get(AssetService)
        self.prettyPrinter: PrettyPrinter = PrettyPrinter_
        prefix: str = self.__class__.meta['prefix']
        add_prefix: bool = self.__class__.meta['add_prefix']
        # prefix =
        if not prefix.startswith(PATH_SEPARATOR) and add_prefix:
            prefix = PATH_SEPARATOR + prefix

        self.router = APIRouter(prefix=prefix, on_shutdown=[self.on_shutdown], on_startup=[
                                self.on_startup], dependencies=dependencies)
        
        self._stack_callback()
        self._set_rate_limit()

        self._add_routes()
        self._add_handcrafted_routes()

        self._mount_included_router()
        self._add_websockets()

        self.default_response: Dict[int | str,
                                    Dict[str, Any]] | None = router_default_response

    def on_startup(self):
        """
        [Important] Ensure to call super when overriding this function 
        """
        for ws in self.websockets.values():
            ws.on_startup()

    async def on_shutdown(self):
        """
        [Important] Ensure to call super when overriding this function 
        """
        for ws in self.websockets.values():
            if asyncio.iscoroutinefunction(ws.on_shutdown):
                await ws.on_shutdown()
            else:
                ws.on_shutdown()

    def _add_routes(self):
        if self.__class__.meta['classname'] not in ROUTES:
            return

        routes_metadata = ROUTES[self.__class__.meta['classname']]
        for route in routes_metadata:
            kwargs = route.copy()
            operation_id = kwargs['operation_id']
            kwargs['endpoint'] = getattr(self, kwargs['endpoint'],)
            self.router.add_api_route(**kwargs)

    def _mount_included_router(self):
        routers = set(self.__class__.meta['routers'])
        routers:list[Type[R]] = list(routers)
        for route in routers:
            r: BaseHTTPRessource = route()
            self.router.include_router(r.router,)

    def _add_websockets(self):
        self.websockets: dict[str, W] = {}
        self.ws_path = []
        w = set(self.__class__.meta['websockets'])
        for WSClass in list(w):
            ws: W = WSClass()
            self.websockets[WSClass.__name__] = ws
            for endpoints in ws.ws_endpoints:
                path: str = endpoints.meta['path']
                if not path.startswith('/'):
                    path = '/' + path
                # if not path.endswith('/'):
                #     path = path + '/'
                name = endpoints.meta['name']
                self.ws_path.append(endpoints.meta['operation_id'])

                self.router.add_websocket_route(path, endpoints, name)

    def _check_ws_path(self, ws_path):
        if ws_path not in self.ws_path:
            raise WSPathNotFoundError

    def _add_handcrafted_routes(self):
        ...

    def _add_router_event(self):
        ...

    @property
    def routeExample(self):
        pass

################################################################                           #########################################################

R = TypeVar('R', bound=BaseHTTPRessource)

def common_class_decorator(cls: Type[R] | Callable, decorator: Callable, handling_func: Callable | tuple[Callable, ...], **kwargs) -> Type[R] | None:

        if type(cls) == HTTPRessourceMetaClass:
            for attr in dir(cls):
                if callable(getattr(cls, attr)) and attr in [end['endpoint'] for end in ROUTES[cls.__name__]]:
                    handler = getattr(cls, attr)
                    if handling_func == None:
                        setattr(cls, attr, decorator(**kwargs)(handler))
                    else:
                        setattr(cls, attr, decorator(
                            *handling_func, **kwargs)(handler))
            return cls
        return None

################################################################                           #########################################################

def HTTPRessource(prefix: str, routers: list[Type[R]] = [], websockets: list[Type[W]] = [], add_prefix=True,mount=True):
    def class_decorator(cls: Type[R]) -> Type[R]:
        # TODO: support module-level injection
        meta: ClassMetaData= cls.meta
        cls.meta['prefix'] = prefix
        cls.meta['routers'] = [r for r in list(set(routers)) if r.meta['mount_ressource']]
        cls.meta['websockets'] = websockets
        cls.meta['add_prefix'] = add_prefix
        cls.meta['mount'] = []
        cls.meta['mount_ressource'] = mount
        meta['ressource_id'] = prefix

        meta['classname'] = cls.__name__

        return cls
    return class_decorator

################################################################                           #########################################################

def UsePermission(*permission_function: Callable[..., bool] | Permission | Type[Permission], default_error: HTTPExceptionParams = None,mount=True):
    if not mount:
        def decorator(func:Callable):
            return func
        return decorator

    empty_decorator = len(permission_function) == 0
    if empty_decorator:
        warnings.warn(
            "No Permission function or object was provided.", NoFunctionProvidedWarning)
        
    permission_function = Helper.filter_type_function(permission_function)

    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        cls = common_class_decorator(func, UsePermission, permission_function)
        if cls != None:
            return cls

        class_name = Helper.get_class_name_from_method(func)
        Helper.add_protected_route_metadata(class_name, func.meta['operation_id'])

        def wrapper(function: Callable):

            @functools.wraps(function)
            async def callback(*args, **kwargs):

                if not SECURITY_FLAG:
                    return await function(*args, **kwargs)

                if empty_decorator:
                    return await function(*args, **kwargs)

                if len(kwargs) < 1:
                    raise HTTPException(
                        status_code=status.HTTP_501_NOT_IMPLEMENTED)

                if SpecialKeyParameterConstant.META_SPECIAL_KEY_PARAMETER in kwargs or SpecialKeyParameterConstant.CLASS_NAME_SPECIAL_KEY_PARAMETER in kwargs:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                                        'message': 'special key used'})

                kwargs_prime = kwargs.copy()
                kwargs_prime[SpecialKeyParameterConstant.CLASS_NAME_SPECIAL_KEY_PARAMETER] = class_name
                kwargs_prime[SpecialKeyParameterConstant.META_SPECIAL_KEY_PARAMETER] = func.meta

                for permission in permission_function:
                    try:
                        if type(permission) == type:
                            flag = await permission().do(*args, **kwargs_prime)
                        elif isinstance(permission, Permission):
                            flag = await permission.do(*args, **kwargs_prime)
                        else:
                            flag = await APIFilterInject(permission)(*args, **kwargs_prime)

                        if flag:
                            continue
                        else:
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN)

                    except PermissionDefaultException as e:
                        if e.response != None and isinstance(e.response,Response):
                            return e.response
                        
                        e.raise_http_exception()

                        if default_error == None:
                            raise HTTPException(
                                status_code=status.HTTP_501_NOT_IMPLEMENTED)
                        raise HTTPException(**default_error)

                return await function(*args, **kwargs)
            return callback
        Helper.appends_funcs_callback(func, wrapper, DecoratorPriority.PERMISSION)
        return func
    return decorator


def UseHandler(*handler_function: Callable[..., Exception | None | Any] | Type[Handler] | Handler, default_error: HTTPExceptionParams = None,mount=True):
    # NOTE it is not always necessary to use this decorator, especially when the function is costly in computation
    if not mount:
        def decorator(func:Callable):
            return func
        return decorator
    
    empty_decorator = len(handler_function) == 0
    if empty_decorator:
        warnings.warn("No Handler function or object was provided.",
                      NoFunctionProvidedWarning)
        
    handler_function = Helper.filter_type_function(handler_function)

    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        cls = common_class_decorator(func, UseHandler, handler_function)
        if cls != None:
            return cls

        wrapper = Helper.stack_decorator(
            handler_function, Handler, empty_decorator, default_error, HandlerDefaultException)

        Helper.appends_funcs_callback(func, wrapper, DecoratorPriority.HANDLER)
        return func
    return decorator


def UseGuard(*guard_function: Callable[..., tuple[bool, str]] | Type[Guard] | Guard, default_error: HTTPExceptionParams = None,mount=True):
    # INFO guards only purpose is to validate the request
    # NOTE:  be mindful of the order
    if not mount:
        def decorator(func:Callable):
            return func
        return decorator

    empty_decorator = len(guard_function) == 0
    if empty_decorator:
        warnings.warn("No Guard function or object was provided.",NoFunctionProvidedWarning)

    guard_function = Helper.filter_type_function(guard_function)

    def decorator(func: Callable | Type[R]) -> Callable | Type[R]:
        cls = common_class_decorator(func, UseGuard, guard_function)
        if cls != None:
            return cls

        def wrapper(target_function: Callable):

            @functools.wraps(target_function)
            async def callback(*args, **kwargs):
                if empty_decorator:
                    return await target_function(*args, **kwargs)

                try:
                    for guard in guard_function:
                        if type(guard) == type:
                            flag, message = await guard().do(*args, **kwargs)

                        elif isinstance(guard, Guard):
                            flag, message = await guard.do(*args, **kwargs)
                        else:
                            flag, message = await APIFilterInject(guard)(*args, **kwargs)

                        if not isinstance(flag, bool) or not isinstance(message, str):
                            raise HTTPException(
                                status_code=status.HTTP_501_NOT_IMPLEMENTED)

                        if not flag:
                            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED, detail=message)

                except GuardDefaultException as e:
                    if e.response != None and isinstance(e.response,Response):
                        return e.response
                    
                    e.raise_http_exception()

                    if default_error == None:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED, detail='Request Validation Aborted')
                    raise HTTPException(**default_error)

                return await target_function(*args, **kwargs)
            return callback

        Helper.appends_funcs_callback(func, wrapper, DecoratorPriority.GUARD)
        return func
    return decorator


def UsePipe(*pipe_function: Callable[..., tuple[Iterable[Any], Mapping[str, Any]] | Any] | Type[Pipe] | Pipe, before: bool = True, default_error: HTTPExceptionParams = None,mount=True):
    """
    be mindful of the order which the pipes function will be called, the list can either be before or after, you can add another decorator, each function must return the same type of value
    """
    if not mount:
        def decorator(func:Callable):
            return func
        return decorator
    
    empty_decorator = len(pipe_function) == 0
    if empty_decorator:
        warnings.warn("No Pipe function or object was provided.",
                      NoFunctionProvidedWarning)
    
    pipe_function = Helper.filter_type_function(pipe_function, before)
    

    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        cls = common_class_decorator(
            func, UsePipe, pipe_function, before=before)
        if cls != None:
            return cls

        def wrapper(function: Callable):

            @functools.wraps(function)
            async def callback(*args, **kwargs):
                try:
                    if before:
                        kwargs_prime = kwargs.copy()
                        for pipe in pipe_function:  # verify annotation
                            if type(pipe) == type:
                                result = await pipe().do(*args, **kwargs_prime)
                            elif isinstance(pipe, Pipe):
                                result = await pipe.do(*args, **kwargs_prime)
                            else:
                                result = await APIFilterInject(pipe)(*args, **kwargs_prime)

                            if result == None:
                                continue

                            if not isinstance(result, dict):
                                raise PipeDefaultException

                            kwargs_prime.update(result)

                        kwargs.update(kwargs_prime)
                        return await function(*args, **kwargs)
                    else:
                        result = await function(*args, **kwargs)
                        for pipe in pipe_function:
                            if type(pipe) == type:
                                result = await pipe(before=False).do(result, **kwargs)
                            elif isinstance(pipe, Pipe):
                                result = await pipe.do(result, **kwargs)
                            else:
                                result = await APIFilterInject(pipe)(result, **kwargs)

                        return result

                except PipeDefaultException as e:
                    if e.response != None and isinstance(e.response,Response):
                        return e.response
                    
                    e.raise_http_exception() 
                    if default_error == None:
                        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    
                    raise HTTPException(**default_error)
            return callback

        Helper.appends_funcs_callback(
            func, wrapper, DecoratorPriority.PIPE, touch=0 if before else 0.5)
        return func
    return decorator


def UseInterceptor(*interceptor_function: Callable[[Iterable[Any], Mapping[str, Any]], Type[R] | Callable], default_error: HTTPExceptionParams = None,mount=True):

    if not mount:
        def decorator(func:Callable):
            return func
        return decorator
    
    empty_decorator = len(interceptor_function) == 0
    if empty_decorator:
        warnings.warn("No Pipe function or object was provided.",NoFunctionProvidedWarning)


    interceptor_function = Helper.filter_type_function(interceptor_function)

    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        cls = common_class_decorator(
            func, UseInterceptor, interceptor_function)
        if cls != None:
            return cls

        wrapper = Helper.stack_decorator(interceptor_function, Interceptor,
                                  empty_decorator, default_error, InterceptorDefaultException)

        Helper.appends_funcs_callback(func, wrapper, DecoratorPriority.INTERCEPTOR)
        return func
    return decorator


def UseRoles(roles: list[Role] = [], excludes: list[Role] = [], options: list[Callable] = []):  # TODO options
    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        cls = common_class_decorator(func, UseRoles, None, roles=roles)
        if cls != None:
            return cls
        roles_ = set(roles)
        excludes_ = set(excludes).difference(roles_)

        try:
            roles_.remove(Role.CUSTOM)
        except KeyError:
            ...

        meta: FuncMetaData | None = getattr(func, 'meta', None)
        if meta is not None:
            if meta['default_role']:
                meta['roles'].clear()
                meta['default_role'] = False

            meta['roles'].update(roles_)
            roles_ = meta['roles']
            meta['excludes'].update(excludes_.difference(roles_))
            meta['options'].extend(options)

        return func
    return decorator

################################################################                           #########################################################


def HTTPStatusCode(code: int | str):
    """
    The `HTTPStatusCode` function is a decorator that sets the HTTP status code for a response based on
    the provided code or code name.
    
    :param code: The `code` parameter in the `HTTPStatusCode` function can be either an integer or a
    string. If it's a string, it represents the name of an HTTP status code. If it's an integer, it
    represents the numerical value of an HTTP status code

    :type code: int | str
    """

    if isinstance(code, str):
        if code not in status.__all__:
            raise AttributeError(f"Code name does not exists")
        else:
            code = status.__getattr__(code)
    elif isinstance(code, int):
        ...
    else:
        raise ValueError

    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        cls = common_class_decorator(func, HTTPStatusCode, code)
        if cls != None:
            return cls

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if 'response' in kwargs and isinstance(kwargs['response'], Response):
                kwargs['response'].status_code = code

            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        return wrapper

    return decorator

################################################################                           #########################################################


def UseLimiter(limit_value:str,scope:str=None,exempt=False,override_defaults=True,exempt_when:Callable=None,error_message:str=None):
    """
    *Description copied from the slowapi library*

    * **limit_value**: rate limit string or a callable that returns a string.
        :ref:`ratelimit-string` for more details.
    * **scope**: a string or callable that returns a string
        for defining the rate limiting scope.
    * **error_message**: string (or callable that returns one) to override the
        error message used in the response.
    * **exempt_when**: function returning a boolean indicating whether to exempt
    the route from the limit
    * **cost**: integer (or callable that returns one) which is the cost of a hit
    * **override_defaults**: whether to override the default limits (default: True)
    """
    if scope!= None and not isinstance(scope,str):
        raise ValueError
    
    shared = scope != None

    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        cls = common_class_decorator(func, UseLimiter, None, limit_value=limit_value,override_defaults=override_defaults,exempt_when=exempt_when,error_message=error_message)
        if cls != None:
            return cls
        meta: FuncMetaData | None = getattr(func, 'meta', None)
        if meta is not None:
            operation_id = meta['operation_id']
            meta['limit_exempt'] = exempt
            meta['limit_obj'] = {'limit_value':limit_value,'override_defaults':override_defaults,'exempt_when':exempt_when,'error_message':error_message,
                                 'cost':bind_cost_request}
            if shared:
                meta['limit_obj']['scope'] = scope
            meta['shared'] = shared
            
        def wrapper(target_function):
            return Helper.response_decorator(target_function)
        
        Helper.appends_funcs_callback(func,wrapper,DecoratorPriority.LIMITER)
        return func

    return decorator


################################################################                           #########################################################

def PingService(services: list[S | dict], infinite_wait=False,is_manager=False,wait_timeout=MIN_TIMEOUT):

    async def inner_callback(route_params:dict):
        for s in services:
            k = {}
            k['__route_params__'] = route_params
            k['__profile__'] =route_params.get('profile',None)
            k['__is_manager__'] = is_manager

            if isinstance(s, dict):
                k.update(s['kwargs'])
                s = s['cls']

            cls: BaseService = Get(s)
            if infinite_wait:
                await BaseService.CheckStatusBeforeHand(cls.async_pingService)(cls,**k)
            else:
                BaseService.CheckStatusBeforeHand(cls.sync_pingService)(cls,**k)

    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        cls = common_class_decorator( func, PingService, None, services=services, infinite_wait=infinite_wait)
        if cls != None:
            return cls

        def wrapper(target_function: Callable):

            @functools.wraps(target_function)
            async def callback(*args, **kwargs):
                
                if not infinite_wait and wait_timeout >= 0:
                    asyncio.wait_for(inner_callback(kwargs), wait_timeout)
                else:
                    await inner_callback(kwargs)
                return await Helper.return_result(target_function,args,kwargs)

            return callback
        Helper.appends_funcs_callback(func, wrapper, DecoratorPriority.HANDLER,PING_SERVICE_TOUCH)
        return func
    
    return decorator

def UseServiceLock(*services: Type[S], lockType: Literal['reader', 'writer'] = 'writer',infinite_wait:bool=False,check_status:bool=True,as_manager:bool = False,miniLockType:Literal['reader', 'writer'] =None,**add_kwargs):
    if lockType not in ['reader', 'writer']:
        raise TypeError
    
    if miniLockType == None:
        miniLockType = lockType

    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        cls = common_class_decorator(func, UseServiceLock, services,lockType=lockType,infinite_wait=infinite_wait,check_status=check_status,as_manager=as_manager,miniLockType=miniLockType,**add_kwargs)
        if cls != None:
            return cls

        def wrapper(target_function: Callable):

            @functools.wraps(target_function)
            async def callback(*args, **kwargs):

                wait_timeout = kwargs.get('wait_timeout',MIN_TIMEOUT)
                as_async = kwargs.get('as_async',True)
                
                def proxy(_service:BaseService|BaseMiniServiceManager,f:Callable):
                    
                    @functools.wraps(f)
                    async def delegator(*a,**k):
                        async with _service.statusLock.reader if lockType == 'reader' else _service.statusLock.writer:
                            if check_status:
                                _service.check_status('')

                            if as_manager:
                                profile = kwargs.get('profile',None)
                                if profile == None:
                                    raise ProfileNotSpecifiedError
                                if profile not in _service.MiniServiceStore:
                                    raise ProfileTypeNotMatchRequest(profile,add_kwargs.get('motor_fallback',False))
                                
                                s:BaseMiniService = _service.MiniServiceStore.get(profile)

                                async with s.statusLock.reader if miniLockType == 'reader' else _service.statusLock.writer:
                                    if check_status:
                                        s.check_status('')
                    
                            return await Helper.return_result(f,a,k)
                    return delegator
                
                inner_callback = target_function

                for s in reversed(services):
                    _service: S = Get(s)
                    inner_callback = proxy(_service,inner_callback)

                if not infinite_wait and wait_timeout >=0 and as_async:
                    return await asyncio.wait_for(inner_callback(*args,**kwargs),wait_timeout)
                else:
                    return await inner_callback(*args,**kwargs)
                #NOTE: This is the only way to wait on the request, the timeout is for the whole request wrapped in the lock instead of only the verification that we wait

            return callback
        Helper.appends_funcs_callback(func, wrapper, DecoratorPriority.HANDLER,STATUS_LOCK_TOUCH)
        return func
    return decorator

################################################################                           #########################################################

def Exclude():
    ...

################################################################                           #########################################################

def MountDirectory(path: str, app: StaticFiles, name: str):
    def class_decorator(cls: Type[R]) -> Type[R]:
        if type(cls) != HTTPRessourceMetaClass:
            return
        meta: ClassMetaData = cls.meta
        meta['mount'].append(
            {
                'app': app,
                'name': name,
                'path': path
            }
        )

        return cls
    return class_decorator


def IncludeRessource(*ressources: Type[R] | R):
    def class_decorator(cls: Type[R]) -> Type[R]:
        if type(cls) != HTTPRessourceMetaClass:
            return

        meta: ClassMetaData = cls.meta
        meta['routers'] = list(set(ressources))

        return cls
    return class_decorator


def IncludeWebsocket(*websocket: Type[W]):
    def class_decorator(cls: Type[R]) -> Type[R]:
        if type(cls) != HTTPRessourceMetaClass:
            return

        meta: ClassMetaData = cls.meta
        meta['websockets'] = list(set(websocket))

        return cls
    return class_decorator
################################################################                           #########################################################
