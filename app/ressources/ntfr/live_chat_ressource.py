from typing import Annotated, AsyncIterable, Literal, Optional

from fastapi import Depends, Query, Request, Response,status
from fastapi.responses import JSONResponse
from fastapi.sse import ServerSentEvent
from pydantic import BaseModel
from app.classes.stream_data_parser import StreamBufferDataParser
from app.container import Get, InjectInMethod
from app.decorators.interceptors import KeepAliveResponseInterceptor
from app.decorators.pipes import RemoteAgentInjectorPipe
from  app.definition._ressource import BaseHTTPRessource, HTTPMethod,HTTPRessource, IncludeWebsocket, PingService, LockService, Throttle, UseGuard, UseHandler, UseInterceptor, UseLimiter, UsePermission, UsePipe, UseRoles
from app.definition._utils_decorator import Guard, Permission
from app.depends.funcs_dep import get_contact_permission
from app.depends.utility_dep import get_agent
from app.depends.variables import binary_callable_factory
from app.manager.keep_alive_manager import KeepAliveManager
from app.services.agent.remote_agent_service import RemoteAgentMiniService, RemoteAgentService
from app.services.database.redis_service import RedisService
from app.services.chat_service import ChatService
from app.services.ntfr.live_chat_service import LiveChatService
from app.services.reactive_service import ReactiveService
from app.services.worker.celery_service import CeleryService
from app.services.setting_service import SettingService
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.security_service import JWTAuthService
from app.websockets.live_chat_ws import LiveChatWebSocket
from app.decorators.handlers import  AgentHandler, AgenticHandler, AsyncIOHandler, ReactiveHandler, RedisHandler, ServiceAvailabilityHandler, StreamDataParserHandler, WebSocketHandler
from app.classes.auth_permission import ChatPermission, ContactPermission, WSPermission,Role
from app.decorators.permissions import JWTRouteHTTPPermission, JWTNonRequiredContactPermission
from app.depends.dependencies import get_auth_permission, get_contact_token, get_request_id
from app.utils.helper import generateId


CHAT_PREFIX= 'chat'

class ChatModel(BaseModel):
    mode:Literal['text','rtc']

class JWTChatTicketPermission(Permission):

    @InjectInMethod()
    def __init__(self,jwtAuthService:JWTAuthService):
        super().__init__()
        self.jwtAuthService = jwtAuthService

    async def permission(self,chatPermission:ChatPermission):
        return super().permission()

class DisconnectionHandler(Handler):
    
    def __int__(self):
        self.configService = Get(ConfigService)
        pass

async def disconnection_handler(function,args,kwargs):
    liveChatService = Get(LiveChatService)

    try:
        ...
    except:
        ...


class ChatSessionAuthGuard(Guard):

    def guard(self,session:str,chatPermission:ChatPermission):
        ...

@UseRoles([Role.CHAT])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler)
@HTTPRessource(prefix=CHAT_PREFIX,websockets=[LiveChatWebSocket])
class LiveChatRessource(BaseHTTPRessource):

    guest_query_callable = binary_callable_factory('guest')
    chat_permission_header = APIBearer()

    @staticmethod
    def get_chat_permission(token:str = Depends(chat_permission_header)):
        if token == None:
            raise HTTPException()

        jwtAuthService = Get(JWTAuthService)
        return jwtAuthService.verify_chat_permission(token)

    @staticmethod
    def get_contact_permission(token:Optional[str]=Depends(get_contact_token))->ContactPermission|None:
        jwtAuthService = Get(JWTAuthService)
        if token == None:
            return None
        return jwtAuthService.verify_contact_permission(token)


    @InjectInMethod()
    def __init__(self,jwtAuthService:JWTAuthService,liveChatService:LiveChatService, configService: ConfigService,contactService:ContactsService,chatService:ChatService,settingService:SettingService,reactiveService:ReactiveService):
        super().__init__()
        self.contactService = contactService
        self.configService = configService
        self.jwtAuthService = jwtAuthService
        self.chatService = chatService
        self.settingService = settingService
        self.reactiveService = reactiveService
        self.liveChatService = liveChatService

    @Throttle()
    @UseLimiter()
    @LockService(SettingService,lockType='reader')
    @UseHandler(WebSocketHandler,RedisHandler,AgentHandler)
    @UsePermission(JWTNonRequiredContactPermission('any',True))
    @LockService(RemoteAgentService,lockType='reader',miniLockType='reader',as_manager=False)
    @BaseHTTPRessource.Get('/permission/',)
    async def chat_permission(self,chat:ChatModel,request:Request,response:Response,contactPermission:ContactPermission|None=Depends(get_contact_permission),request_id:str=Depends(get_request_id),):
        ws_path = '' if chat.mode == 'text' else ''
        self._check_ws_path(ws_path)

        chatPermission = ChatPermission()
        token:str = ...
        session_id:str = ...

    @Throttle()
    @UseGuard(ChatSessionAuthGuard)
    @UseHandler()
    @UseLimiter(key_func='session')
    @UsePermission(JWTChatTicketPermission)
    @UseInterceptor(KeepAliveResponseInterceptor)
    @LockService(RemoteAgentService,lockType='reader',miniLockType='reader',as_manager=True)
    @PingService([{'cls':RemoteAgentService,'kwargs':{'grpc':True,'status':True}}],is_manager=True,infinite_wait=True)
    @UseHandler(WebSocketHandler,RedisHandler,AgenticHandler,AgentHandler,AsyncIOHandler,StreamDataParserHandler,ReactiveHandler)
    @BaseHTTPRessource.HTTPRoute('/{mode}/{agent}/',methods=[HTTPMethod.POST],response_class=AsyncIterable[ServerSentEvent])
    async def enqueue_chat(self,agent:str,keepAlive:Annotated[KeepAliveManager,Depends(KeepAliveManager)],response:Response,request:Request,profile:str=Depends(get_agent),chatPermission:ChatPermission=Depends(get_chat_permission),
                           request_id:str=Depends(get_request_id))->AsyncIterable[ServerSentEvent]:
        
        ws_path = self.get_websocket_path()
        self._check_ws_path(ws_path)

        keepAlive.create_subject('HTTP')
        keepAlive.register_lock()

        def callback(values:list[dict]):
            ...

        keepAlive.set_stream_parser(StreamBufferDataParser(callback))

        yield ServerSentEvent(raw_data=None,event='[OK]',comment='chat room waiting request ok')

        async for states in keepAlive.wait_for():
            yield ServerSentEvent(data=states,event='[STREAM]',comment='sending chat room events')

        run_id = self.websockets[LiveChatWebSocket.__name__].run_id # ERROR Subject to error
        token = self.jwtAuthService.encode_ws_token(run_id,ws_path,self.settingService.CHAT_EXPIRATION)
        yield ServerSentEvent(raw_data=token,event='[DONE]',comment='streaming done')

    @UseGuard(ChatSessionAuthGuard)
    @UsePermission(JWTChatTicketPermission)
    @BaseHTTPRessource.HTTPRoute('/chat/',methods=[HTTPMethod.DELETE])
    async def end_chat(self,response:Response,request:Request,request_id:str=Depends(get_request_id)):
        ...
    
    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.HTTPRoute('/manage/',methods=[HTTPMethod.DELETE],authPermission=Depends(get_auth_permission))
    async def dequeue_chat(self,request:Request,response:Response):
        ...


    @staticmethod
    def get_websocket_path(mode):
        ws_path = '' if mode == 'text' else ''



