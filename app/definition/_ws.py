import functools
from fastapi import WebSocketDisconnect,WebSocketException,WebSocket
#from app.interface.events import EventInterface
#from app.utils.dependencies import get_bearer_token
import json 
import wrapt
from pydantic import BaseModel
from typing import Any, Callable, Type,TypeVar,NewType, Union

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


class WSRessMetaClass(type):
    def __new__(cls, name, bases, dct):
        setattr(cls,'meta',{})
        return super().__new__(cls, name, bases, dct)


WS_METADATA:dict[str,type] = {}


class Protocol(BaseModel):
    __protocol_name:str
    

class BaseWebSocketRessource(metaclass = WSRessMetaClass):

    @staticmethod
    def WSLifecycle(func:Callable):

        @functools.wraps(func)
        def wrapper(*args,**kwargs):
            return func(*args,**kwargs)

        return wrapper
    
    @staticmethod
    def WSEndpoint(path:str,protocol: str | bytes | dict | BaseModel=str):
        ...
    
    @staticmethod
    def WSProtocol(protocol:str | bytes | dict | BaseModel,protocol_definition:Callable[...,Any]):
        
        def decorator(func:Callable):
            return func
        
        return decorator
        
    
    def __init__(self):
        self.path:dict[str,Any] = {}
        self.protocol:dict[str,type] = {}
        self.endpoints:dict = {}
        self.connection_manager = WSConnectionManager()
        self.protocol:dict = {}
    
    def __init_subclass__(cls):
        WS_METADATA[cls.__name__] = cls
        
    def on_connect(self,websocket:WebSocket):
        ...
    
    def on_disconnect(self,websocket:WebSocket):
        ...
    
    def on_shutdown(self):
        ...
    
    def on_startup(self):
        ...


W = TypeVar('W', bound=BaseWebSocketRessource)


@wrapt.decorator
def WebSocketRessource(cls:Type[W])->Type[Union[W,BaseWebSocketRessource]]:
    class Factory(cls,BaseWebSocketRessource):
        ...
    return type(cls.__name__, (cls, BaseWebSocketRessource), dict(Factory.__dict__))
    

def WSGuard():
    ...