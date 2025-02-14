"""
The `BaseResource` class initializes with a `container` attribute assigned from the `CONTAINER`
instance imported from `container`.
"""
from inspect import isclass
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence, TypeVar, Type, TypedDict
from app.definition._ws import W
from app.utils.helper import issubclass_of
from app.utils.constant import SpecialKeyParameterConstant
from app.services.assets_service import AssetService
from app.container import Get, Need
from app.definition._service import S, Service
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from app.utils.prettyprint import PrettyPrinter_, PrettyPrinter
import functools
from fastapi import BackgroundTasks
from app.interface.events import EventInterface
from enum import Enum
from ._utils_decorator import *
from app.classes.auth_permission import FuncMetaData, Role, WSPathNotFoundError
from slowapi import Limiter
from slowapi.util import get_remote_address


PATH_SEPARATOR = "/"
GlobalLimiter = Limiter(get_remote_address) # BUG Need to change the datastructure to have more limiter
RequestLimit =0


def get_class_name_from_method(func: Callable) -> str:
    return func.__qualname__.split('.')[0]


class ClassMetaData(TypedDict):
    prefix:str
    routers:list
    websockets:list[W]



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
"""


def add_protected_route_metadata(class_name: str, operation_id: str):
    if class_name in PROTECTED_ROUTES:
        PROTECTED_ROUTES[class_name].append(operation_id)
    else:
        PROTECTED_ROUTES[class_name] = [operation_id]


def appends_funcs_callback(func: Callable, wrapper: Callable, priority: DecoratorPriority, touch: float = 0):
    class_name = get_class_name_from_method(func)
    if class_name not in DECORATOR_METADATA:
        DECORATOR_METADATA[class_name] = {}

    if func.__name__ not in DECORATOR_METADATA[class_name]:
        DECORATOR_METADATA[class_name][func.__name__] = []

    DECORATOR_METADATA[class_name][func.__name__].append(
        (wrapper, priority.value + touch))


class HTTPMethod(Enum):
    POST = 'POST'
    GET = 'GET'
    UPDATE = 'UPDATE'
    DELETE = 'DELETE'
    PUT = 'PUT'
    PATCH = 'PATCH'
    OPTIONS = 'OPTIONS'
    ALL = 'ALL'

    @staticmethod
    def to_strs(methods: list[Any] | Any):
        if isinstance(methods, HTTPMethod):
            return [methods.value]
        methods: list[HTTPMethod] = methods
        return [method.value for method in methods]
    
class HTTPExceptionParams(TypedDict):
    status_code:int
    detail: Any | None
    headers: dict[str,str] | None = None


class RessourceResponse(TypedDict):
    message:str
    details:Optional[Any]


class HTTPRessourceMetaClass(type):
    def __new__(cls, name, bases, dct):
        #setattr(cls,'meta',{})
        return super().__new__(cls, name, bases, dct)


class BaseHTTPRessource(EventInterface,metaclass=HTTPRessourceMetaClass):

    @staticmethod
    def _build_operation_id(route_name: str, prefix: str, method_name: list[HTTPMethod] | HTTPMethod, operation_id: str) -> str:
        if operation_id != None:
            return operation_id

        m = HTTPMethod.to_strs(method_name) if isinstance(method_name,list) else [method_name]
        return route_name.replace(PATH_SEPARATOR, "_") + '_'.join(m)

    @staticmethod
    def HTTPRoute(path: str, methods: Iterable[HTTPMethod] | HTTPMethod = [HTTPMethod.POST], operation_id: str = None, dependencies:Sequence[Depends]=None, response_model: Any = None, response_description: str = "Successful Response",
                  responses: Dict[int | str, Dict[str, Any]] | None = None,
                  deprecated: bool | None = None):
        def decorator(func: Callable):
            computed_operation_id = BaseHTTPRessource._build_operation_id(path, None, methods, operation_id)
            
            setattr(func,'meta', FuncMetaData())
            func.meta['operation_id'] = computed_operation_id
            func.meta['roles'] = set()
            func.meta['excludes'] = set()
            func.meta['options'] =[] 
            func.meta['limit_obj'] =None
            
            class_name = get_class_name_from_method(func)
            kwargs = {
                'path': path,
                'endpoint': func.__name__,
                'operation_id': operation_id,
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
    def Get(path: str, operation_id: str = None, dependencies:Sequence[Depends]=None, response_model: Any = None, response_description: str = "Successful Response",
            responses: Dict[int | str, Dict[str, Any]] | None = None,
            deprecated: bool | None = None):
        return BaseHTTPRessource.HTTPRoute(path, [HTTPMethod.GET], operation_id,dependencies, response_model, response_description, responses, deprecated)

    @staticmethod
    def Post(path: str, operation_id: str = None,  dependencies:Sequence[Depends]=None,response_model: Any = None, response_description: str = "Successful Response",
             responses: Dict[int | str, Dict[str, Any]] | None = None,
             deprecated: bool | None = None):
        return BaseHTTPRessource.HTTPRoute(path, [HTTPMethod.POST], operation_id, dependencies, response_model, response_description, responses, deprecated)
    
    @staticmethod
    def Delete(path: str, operation_id: str = None, dependencies:Sequence[Depends]=None, response_model: Any = None, response_description: str = "Successful Response",
             responses: Dict[int | str, Dict[str, Any]] | None = None,
             deprecated: bool | None = None):
        return BaseHTTPRessource.HTTPRoute(path, [HTTPMethod.DELETE], operation_id, dependencies,  response_model, response_description, responses, deprecated)

    def _stack_callback(self):
        if self.__class__.__name__ not in DECORATOR_METADATA:
            return
        M = DECORATOR_METADATA[self.__class__.__name__]
        for f in M:
            if hasattr(self, f):
                stacked_callback = M[f].copy()
                c = getattr(self, f)
                for sc in sorted(stacked_callback, key=lambda x: x[1], reverse=True):
                    sc_ = sc[0]
                    c = sc_(c)
                setattr(self, f, c)
    
    def _set_rate_limit(self):
        for end in ROUTES[self.__class__.__name__]:
            func_name = end['endpoint']
            func_attr = getattr(self,func_name)
            meta:FuncMetaData = getattr(func_attr,'meta')
            limit_obj = meta['limit_obj']
            if limit_obj:
                func_attr = GlobalLimiter.limit(**limit_obj)(func_attr)
                setattr(self,func_name,func_attr)


    def __init_subclass__(cls: Type) -> None:

        RESSOURCES[cls.__name__] = cls
        # ROUTES[cls.__name__] = []
        setattr(cls, 'meta', {})
        super().__init_subclass__()

    def __init__(self,dependencies=None,router_default_response:dict=None) -> None:
        self.assetService: AssetService = Get(AssetService)
        self.prettyPrinter: PrettyPrinter = PrettyPrinter_
        prefix:str = self.__class__.meta['prefix']
        #prefix = 
        if not prefix.startswith(PATH_SEPARATOR):
            prefix = PATH_SEPARATOR + prefix
        
        self.router = APIRouter(prefix=prefix, on_shutdown=[self.on_shutdown], on_startup=[self.on_startup],dependencies=dependencies)
        self._set_rate_limit()
        self._stack_callback()

        self._add_routes()
        self._add_handcrafted_routes()

        self._mount_included_router()
        self._add_websockets()

        self.default_response: Dict[int | str, Dict[str, Any]] | None = router_default_response

    def get(self, dep: Type[S], scope=None, all=False) -> Type[S]:
        return Get(dep, scope, all)

    def need(self, dep: Type[S]) -> Type[S]:
        return Need(dep)

    def on_startup(self):
        """
        [Important] Ensure to call super when overriding this function 
        """
        for ws in self.websockets.values():
            ws.on_startup()
        
    def on_shutdown(self):
        """
        [Important] Ensure to call super when overriding this function 
        """
        for ws in self.websockets.values():
            ws.on_shutdown()

    def _add_routes(self):
        if self.__class__.__name__ not in ROUTES:
            return

        routes_metadata = ROUTES[self.__class__.__name__]
        for route in routes_metadata:
            kwargs = route.copy()
            operation_id = kwargs['operation_id']
            kwargs['endpoint'] = getattr(self, kwargs['endpoint'],)
            self.router.add_api_route(**kwargs)
    
    def _mount_included_router(self):
        routers = set(self.__class__.meta['routers'])
        for route in list(routers):
            r:BaseHTTPRessource = route()
            self.router.include_router(r.router,)
    
    def _add_websockets(self):
        self.websockets:dict[str,W] = {}
        self.ws_path = []
        w = set(self.__class__.meta['websockets'])
        for WS_Class in list(w):
            ws:W = WS_Class()
            self.websockets[WS_Class.__name__] = ws
            for endpoints in ws.ws_endpoints:
                path:str = endpoints.meta['path']                
                if not path.startswith('/'):
                    path = '/' + path
                # if not path.endswith('/'):
                #     path = path + '/'
                name = endpoints.meta['name']
                self.ws_path.append(endpoints.meta['operation_id'])

                self.router.add_websocket_route(path,endpoints,name)
        
    def _check_ws_path(self,ws_path):
        if ws_path not in self.ws_path:
            raise WSPathNotFoundError

    def _add_handcrafted_routes(self):
        ...

    def _add_event(self):
        ...

    @property
    def routeExample(self):
        pass


R = TypeVar('R', bound=BaseHTTPRessource)


def HTTPRessource(prefix:str,routers:list[Type[R]]=[],websockets:list[Type[W]]=[]):
    def class_decorator(cls:Type[R]) ->Type[R]:
        # TODO: support module-level injection 
        cls.meta['prefix'] = prefix
        cls.meta['routers'] = routers
        cls.meta['websockets'] = websockets
        return cls
    return class_decorator

def common_class_decorator(cls: Type[R] | Callable, decorator: Callable, handling_func: Callable | tuple[Callable, ...], **kwargs) -> Type[R] | None:
    
    if type(cls) == HTTPRessourceMetaClass:
        for attr in dir(cls):
            if callable(getattr(cls, attr)) and attr in [end['endpoint'] for end in ROUTES[cls.__name__]]:
                handler = getattr(cls, attr)
                if handling_func == None:
                    setattr(cls, attr, decorator(**kwargs)(handler))
                else:
                    setattr(cls, attr, decorator(*handling_func, **kwargs)(handler))  # BUG can be an source of error if not a tuple
        return cls
    return None


def UsePermission(*permission_function: Callable[..., bool] | Permission | Type[Permission], default_error: HTTPExceptionParams =None):

    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        cls = common_class_decorator(func, UsePermission, permission_function)
        if cls != None:
            return cls

        class_name = get_class_name_from_method(func)
        add_protected_route_metadata(class_name, func.meta['operation_id'])

        def wrapper(function: Callable):

            @functools.wraps(function)
            def callback(*args, **kwargs):

                if len(kwargs) < 1:
                    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)

                if SpecialKeyParameterConstant.META_SPECIAL_KEY_PARAMETER in kwargs or SpecialKeyParameterConstant.CLASS_NAME_SPECIAL_KEY_PARAMETER in kwargs:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail={'message':'special key used'})
                
                kwargs_prime = kwargs.copy()
                kwargs_prime[SpecialKeyParameterConstant.CLASS_NAME_SPECIAL_KEY_PARAMETER] = class_name
                kwargs_prime[SpecialKeyParameterConstant.META_SPECIAL_KEY_PARAMETER] = func.meta
                
                # TODO use the prefix here
                for permission in permission_function:
                    try:
                        if type(permission) == type:
                            flag = permission().do(*args, **kwargs_prime)
                        elif isinstance(permission, Permission):
                            flag = permission.do(*args, **kwargs_prime)
                        else:
                            flag = permission(*args, **kwargs_prime)
                        
                        if flag:
                            continue
                        else:
                            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
                        
                    except PermissionDefaultException:
                        if default_error== None:
                            raise HTTPException( status_code=status.HTTP_501_NOT_IMPLEMENTED)
                        raise HTTPException(**default_error)
                    
                return function(*args, **kwargs)
            return callback
        appends_funcs_callback(func, wrapper, DecoratorPriority.PERMISSION)
        return func
    return decorator

def UseHandler(*handler_function: Callable[..., Exception | None| Any] | Type[Handler] | Handler, default_error: HTTPExceptionParams =None):
    # NOTE it is not always necessary to use this decorator, especially when the function is costly in computation

    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        cls = common_class_decorator(func, UseHandler, handler_function)
        if cls != None:
            return cls

        def wrapper(function: Callable):

            @functools.wraps(function)
            def callback(*args, **kwargs): # Function that will be called 
                if len(handler_function) == 0:
                    # TODO print a warning
                    return function(*args, **kwargs)
                

                def handler_proxy(handler,f:Callable):

                    def delegator(*a,**k):
                        if type(handler) == type:
                            handler_obj:Handler = handler()
                            return handler_obj.do(f, *a, **k)
                        elif isinstance(handler, Handler):
                            return handler.do(f, *a, **k)
                        else:
                            return handler(f, *a, **k)
                    return delegator
                    
                handler_prime = function
                for handler in reversed(handler_function):
                    handler_prime = handler_proxy(handler,handler_prime)
                     
                try:
                    return handler_prime(*args, **kwargs)
                except HandlerDefaultException as e:

                    if default_error == None:
                        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail='Could not correctly treat the error')
                
                    raise HTTPException(**default_error)
                
            return callback
        appends_funcs_callback(func, wrapper, DecoratorPriority.HANDLER)
        return func
    return decorator

def UseGuard(*guard_function: Callable[..., tuple[bool, str]] | Type[Guard] | Guard, default_error: HTTPExceptionParams =None):
    # INFO guards only purpose is to validate the request
    # NOTE:  be mindful of the order

    # BUG notify the developper if theres no guard_function mentioned
    def decorator(func: Callable | Type[R]) -> Callable | Type[R]:
        cls = common_class_decorator(func, UseGuard, guard_function)
        if cls != None:
            return cls

        def wrapper(target_function: Callable):

            @functools.wraps(target_function)
            def callback(*args, **kwargs):

                for guard in guard_function:

                    # BUG check annotations of the guard function
                    if type(guard) == type :
                        flag, message = guard().do(*args, **kwargs)
                    
                    elif issubclass_of(Guard,type(guard)):
                        flag, message = guard.do(*args, **kwargs)
                    else:
                        flag, message = guard(*args, **kwargs)

                    if not flag:
                        if default_error == None:   
                            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED, detail=message)
                        raise HTTPException(**default_error)

                return target_function(*args, **kwargs)
            return callback

        appends_funcs_callback(func, wrapper, DecoratorPriority.GUARD)
        return func
    return decorator

def UsePipe(*pipe_function: Callable[..., tuple[Iterable[Any], Mapping[str, Any]]| Any] | Type[Pipe] | Pipe, before: bool = True, default_error: HTTPExceptionParams =None):
    # NOTE be mindful of the order which the pipes function will be called, the list can either be before or after, you can add another decorator, each function must return the same type of value

    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        cls = common_class_decorator(func, UsePipe, pipe_function, before=before)
        if cls != None:
            return cls

        def wrapper(function: Callable):

            @functools.wraps(function)
            def callback(*args, **kwargs):
                try:
                    if before:
                        kwargs_prime = kwargs.copy()
                        for pipe in pipe_function:  # verify annotation
                            if type(pipe) == type:
                                result = pipe().do(*args, **kwargs_prime)
                            elif isinstance(pipe, Pipe):
                                result = pipe.do(*args, **kwargs_prime)
                            else:
                                result = pipe(*args, **kwargs_prime)

                            if not isinstance(result,dict):
                                raise PipeDefaultException
                            
                            kwargs_prime.update(result)
                        
                        kwargs.update(kwargs_prime)
                        return function(*args, **kwargs)
                    else:
                        result = function(*args, **kwargs)
                        for pipe in pipe_function:
                            if type(pipe) == type:
                                result = pipe(before=False).do(result)
                            elif isinstance(pipe, Pipe):
                                result = pipe.do(result)
                            else:
                                result = pipe(result)

                        return result
                
                except PipeDefaultException:
                    if default_error == None:
                        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    raise HTTPException(**default_error)
            return callback

        appends_funcs_callback(func, wrapper, DecoratorPriority.PIPE,touch=0 if before else 0.5)  # TODO 3 or 3.5 if before
        return func
    return decorator

def UseInterceptor(interceptor_function: Callable[[Iterable[Any], Mapping[str, Any]], Type[R] | Callable], default_error: HTTPExceptionParams =None):
    raise NotImplementedError

    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        cls = common_class_decorator(
            func, UseInterceptor, interceptor_function)
        if cls != None:
            return cls

        def wrapper(function: Callable):
            @functools.wraps(function)
            def callback(*args, **kwargs):
                return interceptor_function(function, *args, **kwargs)
            return callback

        appends_funcs_callback(func, wrapper, DecoratorPriority.INTERCEPTOR)
        return func
    return decorator

def UseRoles(roles:list[Role]=[],excludes:list[Role]=[],options:list[Callable]=[]): # TODO options
    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        cls = common_class_decorator(func, UseRoles,None,roles=roles)
        if cls != None:
            return cls

        roles_ = set(roles)
        excludes_ = set(excludes).difference(roles_)

        try:
            roles_.remove(Role.CUSTOM)
        except KeyError:
            ...

        meta:FuncMetaData | None = getattr(func,'meta',None)
        if meta is not None:
            meta['roles'].update(roles_)
            roles_ = meta['roles']
            meta['excludes'].update(excludes_.difference(roles_))
            meta['options'].extend(options)

        return func
    return decorator

@functools.wraps(GlobalLimiter.limit)
def UseLimiter(**kwargs): #TODO
    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        cls = common_class_decorator(func, UseLimiter,None,**kwargs)
        if cls != None:
            return cls
        meta:FuncMetaData | None = getattr(func,'meta',None)
        if meta is not None:
            meta['limit_obj'] = kwargs
            limit_value:str = kwargs['limit_value']
            try:
                limit_value = int(limit_value.split('/')[0])
                global RequestLimit
                RequestLimit+= limit_value
            except:
                ...
        return func
    return decorator

def PingService(services:list[S]):

    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        cls = common_class_decorator(func,PingService,None,services=services)
        if cls != None:
            return cls
        
        @functools.wraps(func)
        def wrapper(*args,**kwargs):
            for s in services:
                s: Service = Get(s)
                s.pingService()
            
            return func(*args,**kwargs)
        
        return wrapper
    return decorator


def Exclude():
    ...
    
def IncludeRessource(*ressources: Type[R]| R):
    def class_decorator(cls:Type[R]) ->Type[R]:
        if type(cls)!=HTTPRessourceMetaClass:
            return
        
        meta:ClassMetaData =cls.meta
        meta['routers'] = list(set(ressources))
        
        return cls
    return class_decorator

def IncludeWebsocket(*websocket: Type[W]):
    def class_decorator(cls:Type[R]) ->Type[R]:
        if type(cls)!=HTTPRessourceMetaClass:
            return 

        meta:ClassMetaData =cls.meta
        meta['websockets'] = list(set(websocket))

        return cls
    return class_decorator