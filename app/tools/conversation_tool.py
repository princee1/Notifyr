from app.definition._tool import Tool
from app.services.config_service import ConfigService
from app.services.database.mongoose_service import MongooseService

class ConversationTool(Tool):
    
    def __init__(self,configService:ConfigService,mongooseService:MongooseService):
        super().__init__()
        self.configService = configService
        self.mongooseService = mongooseService
    