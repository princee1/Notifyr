from app.definition._service import ServiceClass,Service
from .database_service import MongooseService


@ServiceClass
class ChatService(Service):
    def __init__(self,mongooseService:MongooseService) -> None:
        super().__init__()
        self.mongooseService = mongooseService
    pass


@ServiceClass
class SupportService(Service):
    def __init__(self,chatService:ChatService) -> None:
        super().__init__()
        self.chatService = chatService
    pass



