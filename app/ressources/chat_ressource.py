from app.container import InjectInMethod
from app.definition._ressource import BaseHTTPRessource, HTTPRessource, UseLimiter
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
    @BaseHTTPRessource.HTTPRoute('/interrupt/',)
    async def interrupt(self,):
        ...
    
    @UseLimiter('100/seconds',key_func='public')
    @BaseHTTPRessource.HTTPRoute('/memory/',)
    async def memory(self):
        ...

chat_ressource:list[type[BaseHTTPRessource]] = [AdminChatRessource,PublicChatRessource]

@HTTPRessource('chat',routers=chat_ressource)
class ChatRessource(BaseHTTPRessource):
    ...

    async def options(self):
        ...