from enum import Enum
import functools
import time
from fastapi import HTTPException, WebSocketDisconnect,WebSocketException,WebSocket,status
from app.classes.auth_permission import WSPermission
from app.container import InjectInMethod
from app.interface.events import EventInterface
from app.services.security_service import JWTAuthService
from app.utils.dependencies import get_bearer_token,APIFilterInject
import wrapt
from pydantic import BaseModel
from typing import Any, Callable, Optional, Type,TypeVar,Union,TypedDict,Literal
from app.utils.prettyprint import PrettyPrinter_

#########################################                ##############################################

class WSConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

#########################################                ##############################################

class WSMetaData(TypedDict):
    ...

class FuncMetaData(TypedDict):
    path:str
    protocol_name:Optional[str]

class WSRessMetaClass(type):
    def __new__(cls, name, bases, dct):
        return super().__new__(cls, name, bases, dct)


WS_METADATA:dict[str,type] = {}

#########################################                ##############################################

HandlerType = Literal['current','handler','both']

class BaseProtocol(BaseModel):
    protocol_name:str

    

class WSIdentity:
    ...
    

class BaseWebSocketRessource(EventInterface,metaclass = WSRessMetaClass):

    @staticmethod
    def WSEndpoint(path:str,type_: str | bytes | dict | BaseModel |BaseProtocol=str,name:str = None,path_conn_manager:str=None,handler:HandlerType='current'):

        def decorator(func:Callable):
            if not hasattr(func,'meta'):
                setattr(func,'meta',{})
            
            func.meta['path'] = path
            func.meta['name'] = name
            func.meta['operation_id'] = BaseWebSocketRessource.build_operation_id(path,name)

            @functools.wraps(func)
            async def wrapper(*args,**kwargs):
                path_conn_manager_ = path if path_conn_manager is None else path_conn_manager
                self: BaseWebSocketRessource = args[0]
                manager = self.connection_manager[path_conn_manager_]
                
                websocket:WebSocket= APIFilterInject(self._websocket_injector)(*args,**kwargs)
                kwargs_star = kwargs.copy()
                kwargs_star['operation_id'] = func.meta['operation_id']
                kwargs_star['manager'] = manager

                flag = APIFilterInject(self.on_connect)(*args,**kwargs_star)
                
                if not flag:
                    return
                await manager.connect()
                try:
                    while True:
                        if type_ == str:
                            message:str = await websocket.receive_text()
                            kwargs_star['message'] = message
                            return  APIFilterInject(func)(*args,**kwargs_star)
                        elif type_ == bytes:
                            message:bytes = await websocket.receive_bytes()
                            kwargs_star['message'] = message
                            return  APIFilterInject(func)(*args,**kwargs_star)
                        elif type_ == dict:
                            message:dict = await websocket.receive_json()
                            kwargs_star['message'] = message
                            return  APIFilterInject(func)(*args,**kwargs_star)
                        elif type_ == BaseModel:
                            message:dict = await websocket.receive_json()
                            kwargs_star['message'] = message
                            ... # TODO verify
                            return  APIFilterInject(func)(*args,**kwargs_star)
                        elif type_ == BaseProtocol:
                            ... # TODO verify
                            message:BaseProtocol = await websocket.receive_json()
                            kwargs_star['message'] = message
                            c_result = APIFilterInject(func)(*args,**kwargs_star)
                            h_protocol =APIFilterInject(self.protocol[message['protocol_name']])(message)

                            if handler =='current':
                                return c_result
                            if handler =='handler':
                                return h_protocol 
                            
                            return self._hybrid_protocol_handler(c_result,h_protocol)

                except WebSocketDisconnect:
                    APIFilterInject(self.on_disconnect)(*args,**kwargs_star)
                    manager.disconnect()

            return wrapper

        return decorator     
    
    @staticmethod
    def WSProtocol(protocol_name:str | Enum):
        def decorator(func:Callable):
            if not hasattr(func,'meta'):
                setattr(func,'meta',{})
            proto_name = protocol_name if isinstance(protocol_name,str) else protocol_name.value
            func.meta['protocol_name'] = proto_name
            return func
        
        return decorator

    @staticmethod
    def build_operation_id(path:str):
        ...

    @InjectInMethod
    def __init__(self,jwtAuthService:JWTAuthService):
        self.connection_manager:dict[str,WSConnectionManager] = {}
        self.protocol:dict[str,Callable]={}
        self.ws_endpoints:list[tuple[str,Callable]] =[]

        self.jwtAuthService = jwtAuthService
        self.prettyPrinter = PrettyPrinter_
        self._register_protocol()
    
    def __init_subclass__(cls):
        WS_METADATA[cls.__name__] = cls
        setattr(cls,'meta',WSMetaData())
        
    def _register_protocol(self,):
         for attr in dir(self.__class__):
            method = getattr(self.__class__, attr)
            if callable(method) and hasattr(method,'meta'):
                if 'protocol_name' in method.meta:
                    proto_name = method.meta['protocol_name']
                    self.protocol[proto_name] = method
                
                if 'path' in method.meta:
                    self.ws_endpoints.append(method)
    
    def _websocket_injector(websocket:WebSocket):
        """
        DO NOT MODIFY THIS FUNCTION
        """
        return websocket
                
    def on_connect(self,websocket:WebSocket,operation_id:str):
        auth_token = websocket.headers.get() # TODO find a key name
        
        if auth_token == None:
            return False
        try:
            permission:WSPermission = self.jwtAuthService.decode_token(auth_token)
        except HTTPException as e:
            return False

        if operation_id!= permission['operation_id']:
            return False
        
        if permission['expired_at'] < time.time():
            return False
        
        return True
     
    def on_disconnect(self,websocket:WebSocket):
        ...
    
    def on_shutdown(self):
        ...
    
    def on_startup(self):
        ...

    def _hybrid_protocol_handler(self,c_result:Any,h_protocol_result:Any):
        return 

W = TypeVar('W', bound=BaseWebSocketRessource)


def WebSocketRessource(cls:Type[W])->Type[Union[W,BaseWebSocketRessource]]:
    class Factory(cls,BaseWebSocketRessource):
        ...
    return type(cls.__name__, (cls, BaseWebSocketRessource), dict(Factory.__dict__))
    

def WSGuard():
    ...

def WSHandler():
    ...

#########################################                ##############################################
