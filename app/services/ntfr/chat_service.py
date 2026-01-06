from app.definition._service import Service,BaseService
from app.services.database.mongoose_service import MongooseService


@Service()
class ChatService(BaseService):
    def __init__(self,mongooseService:MongooseService) -> None:
        super().__init__()
        self.mongooseService = mongooseService
    pass


@Service()
class SupportService(BaseService):
    def __init__(self,chatService:ChatService) -> None:
        super().__init__()
        self.chatService = chatService
    pass



