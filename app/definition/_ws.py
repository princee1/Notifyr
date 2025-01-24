from fastapi import WebSocketDisconnect,WebSocketException,WebSocket
from app.utils.dependencies import get_bearer_token
import json 
from pydantic import BaseModel
from typing import Type,TypeVar

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
    ...



class BaseWebSocketRessource(metaclass = WSRessMetaClass):


    @staticmethod
    def WSLifestyle():
        ...

    @staticmethod
    def OnEvent():
        ... 

    @staticmethod
    def WSEndpoint():
        ...
    
    def __init__(self):
        #self.connection_manager = WSConnectionManager()
        self.endpoints:dict = {}
        self.events:dict = {}

    
    


W = TypeVar('W', bound=BaseWebSocketRessource)



def WebSocketRessource():
    ...


def WSGuard():
    ...

def WSHandler():
    ...
