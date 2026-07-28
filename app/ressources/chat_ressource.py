from app.container import InjectInMethod
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UseLimiter
from app.services.chat_service import ChatService
from app.services.config_service import ConfigService
from app.services.database.mongoose_service import MongooseService

@HTTPRessource()
class AdminChatRessource(BaseHTTPRessource):
    
    @InjectInMethod()
    def __init__(self,mongooseService:MongooseService,configService:ConfigService,chatService:ChatService):
        super().__init__(None,None)
        self.mongooseService = mongooseService
        self.configService = configService

    async def fetch_message(self):
        ...
    
    async def delete_message(self):
        ...

    async def fetch_analytics(self):
        ...
 
@HTTPRessource()
class PublicChatRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,mongooseService:MongooseService,configService:ConfigService,chatService:ChatService):
        super().__init__(None,None)
        self.mongooseService = mongooseService
        self.configService = configService
        self.chatService = chatService
    
    @UseLimiter('100/seconds',key_func='public')
    @BaseHTTPRessource.HTTPRoute('/interrupt/',methods=[HTTPMethod.POST])
    async def fetch_interrupt(self,):
        ...
    
    @UseLimiter('100/seconds',key_func='public')
    @BaseHTTPRessource.HTTPRoute('/interrupt/',methods=[HTTPMethod.GET])
    async def resume_interrupt(self,):
        ...
    
    @UseLimiter('100/seconds',key_func='public')
    @BaseHTTPRessource.HTTPRoute('/memory/',methods=[HTTPMethod.GET])
    async def memory(self):
        ...
    
    @UseLimiter('100/seconds',key_func='public')
    @BaseHTTPRessource.HTTPRoute('/graph/',methods=[HTTPMethod.GET])
    async def graph(self):
        ...

chat_ressource:list[type[BaseHTTPRessource]] = [AdminChatRessource,PublicChatRessource]

@HTTPRessource('chat',routers=chat_ressource)
class ChatRessource(BaseHTTPRessource):
    ...

    async def options(self):
        ...