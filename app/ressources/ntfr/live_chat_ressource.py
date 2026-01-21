from fastapi import Depends, Query,status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.container import Get, InjectInMethod
from  app.definition._ressource import BaseHTTPRessource, HTTPMethod,HTTPRessource, IncludeWebsocket, PingService, UseServiceLock, UseHandler, UsePermission, UseRoles
from app.services.database.redis_service import RedisService
from app.services.ntfr.chat_service import ChatService
from app.services.reactive_service import ReactiveService
from app.services.worker.celery_service import CeleryService
from app.services.setting_service import SettingService
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.security_service import JWTAuthService
from app.websockets.chat_ws import ChatWebSocket
from app.decorators.handlers import  ServiceAvailabilityHandler, WebSocketHandler
from app.classes.auth_permission import WSPermission,Role
from app.decorators.permissions import JWTRouteHTTPPermission
from app.depends.dependencies import get_auth_permission
from app.utils.helper import generateId


CHAT_PREFIX= 'chat'

class ChatModel(BaseModel):
    ...

@UseRoles([Role.CHAT])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler)
@HTTPRessource(prefix=CHAT_PREFIX,websockets=[ChatWebSocket])
class LiveChatRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,jwtAuthService:JWTAuthService, configService: ConfigService,contactService:ContactsService,chatService:ChatService,settingService:SettingService,reactiveService:ReactiveService):
        super().__init__()
        self.contactService = contactService
        self.configService = configService
        self.jwtAuthService = jwtAuthService
        self.chatService = chatService
        self.settingService = settingService
        self.reactiveService = reactiveService
    
    @UseServiceLock(SettingService,lockType='reader')
    @UseHandler(WebSocketHandler)
    @BaseHTTPRessource.Get('/live-chat-permission/{ws_path}',)
    def issue_chat_permission(self, ws_path:str):

        self._check_ws_path(ws_path)
        run_id = self.websockets[ChatWebSocket.__name__].run_id
        token = self.jwtAuthService.encode_ws_token(run_id,ws_path,self.settingService.CHAT_EXPIRATION)
        return JSONResponse(status_code=status.HTTP_201_CREATED,content={
            'chat-token':token,
        })

    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
    async def enqueue_chat(self):
        ...
    
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.DELETE])
    async def end_chat(self):
        ...

    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.DELETE],authPermission=Depends(get_auth_permission))
    async def dequeue_chat(self):
        ...
    
    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.GET],authPermission=Depends(get_auth_permission))
    async def check_priority(self):
        ...

    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.PUT],authPermission=Depends(get_auth_permission))
    async def modify_priority(self):
        ...



