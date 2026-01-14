

from fastapi import WebSocket
from app.container import InjectInMethod
from app.definition._ws import BaseProtocol, BaseWebSocketRessource, WebSocketRessource
from app.services.ntfr.chat_service import ChatService
from app.services.ntfr.twilio_service import CallService


class TwilioProtocol(BaseProtocol):
    ...

@WebSocketRessource
class StreamVoiceWebSocket(BaseWebSocketRessource):
    
    @InjectInMethod()
    def __init__(self,chatService:ChatService,callService:CallService):
        super().__init__()
        self.chatService = chatService
        self.callService = callService

    @BaseWebSocketRessource.WSEndpoint('stream-call/{chat_id}',TwilioProtocol,set_protocol_key='event')
    def voice_endpoint(self,websocket:WebSocket,chat_id:str):
        ...

    @BaseWebSocketRessource.WSProtocol('connected')
    def on_call_connect(self,chat_id:str,message:TwilioProtocol):
        ...
    
    @BaseWebSocketRessource.WSProtocol('stop')
    def on_call_stop(self,chat_id:str,message:TwilioProtocol):
        ...

    @BaseWebSocketRessource.WSProtocol('start')
    def on_call_start(self,chat_id:str,message:TwilioProtocol):
        ...
    
    @BaseWebSocketRessource.WSProtocol('media')
    def on_call_media(self,chat_id:str,message:TwilioProtocol):
        ...

    

