from typing import Annotated, AsyncIterable

from fastapi import Depends, Query, Request, Response,status
from fastapi.responses import JSONResponse
from fastapi.sse import ServerSentEvent
from pydantic import BaseModel
from app.classes.stream_data_parser import StreamBufferDataParser
from app.container import Get, InjectInMethod
from app.decorators.interceptors import KeepAliveResponseInterceptor
from app.decorators.pipes import RemoteAgentInjectorPipe
from  app.definition._ressource import BaseHTTPRessource, HTTPMethod,HTTPRessource, IncludeWebsocket, PingService, LockService, Throttle, UseHandler, UseInterceptor, UseLimiter, UsePermission, UsePipe, UseRoles
from app.depends.utility_dep import get_agent
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
from app.classes.auth_permission import WSPermission,Role
from app.decorators.permissions import JWTRouteHTTPPermission
from app.depends.dependencies import get_auth_permission, get_request_id
from app.utils.helper import generateId


CHAT_PREFIX= 'chat'

class ChatModel(BaseModel):
    ...

@UseRoles([Role.CHAT])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler)
@HTTPRessource(prefix=CHAT_PREFIX,websockets=[LiveChatWebSocket])
class LiveChatRessource(BaseHTTPRessource):

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
    @UseLimiter(key_func='session')
    @UseHandler(WebSocketHandler)
    @LockService(SettingService,lockType='reader')
    @BaseHTTPRessource.Get('/permission/{ws_path}/',)
    def chat_permission(self, ws_path:str,request_id:str=Depends(get_request_id)):
        self._check_ws_path(ws_path)

        ...

    @Throttle()
    @UseLimiter()
    @UsePermission()
    @UsePipe(RemoteAgentInjectorPipe)
    @UseInterceptor(KeepAliveResponseInterceptor)
    @LockService(RemoteAgentService,lockType='reader',miniLockType='reader',as_manager=True)
    @PingService([{'cls':RemoteAgentService,'kwargs':{'grpc':True,'status':True}}],is_manager=True,infinite_wait=True)
    @UseHandler(WebSocketHandler,RedisHandler,AgenticHandler,AgentHandler,AsyncIOHandler,StreamDataParserHandler,ReactiveHandler)
    @BaseHTTPRessource.HTTPRoute('/{mode}/{agent}/',methods=[HTTPMethod.POST],response_class=AsyncIterable[ServerSentEvent])
    async def enqueue_chat(self,agent:Annotated[RemoteAgentMiniService,Depends(get_agent)],keepAlive:Annotated[KeepAliveManager,Depends(KeepAliveManager)],response:Response,request:Request,profile:str=Depends(get_agent),request_id:str=Depends(get_request_id))->AsyncIterable[ServerSentEvent]:

        self._check_ws_path(ws_path)

        keepAlive.create_subject('HTTP')
        keepAlive.register_lock()

        def callback(values:list[dict]):
            ...

        keepAlive.set_stream_parser(StreamBufferDataParser(callback))

        yield ServerSentEvent(raw_data=None,event='[OK]',comment='chat room waiting request ok')

        async for states in keepAlive.wait_for():
            yield ServerSentEvent(data=states,event='[STREAM]',comment='sending chat room events')

        run_id = self.websockets[LiveChatWebSocket.__name__].run_id
        token = self.jwtAuthService.encode_ws_token(run_id,ws_path,self.settingService.CHAT_EXPIRATION)
        yield ServerSentEvent(raw_data=token,event='[DONE]',comment='streaming done')

    @UsePermission()
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.DELETE])
    async def end_chat(self,response:Response,request:Request,request_id:str=Depends(get_request_id)):
        ...


    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.HTTPRoute('/manage/',methods=[HTTPMethod.DELETE],authPermission=Depends(get_auth_permission))
    async def dequeue_chat(self,request:Request,response:Response):
        ...
    
    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.HTTPRoute('/manage/',methods=[HTTPMethod.GET],authPermission=Depends(get_auth_permission))
    async def check_priority(self,request:Request,response:Response):
        ...

    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.HTTPRoute('/admin/',methods=[HTTPMethod.PUT],authPermission=Depends(get_auth_permission))
    async def modify_priority(self,request:Request,response:Response):
        ...



