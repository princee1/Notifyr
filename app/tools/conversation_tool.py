from app.definition._tool import ContextPipelineTool, Tool
from app.services.config_service import ConfigService
from app.services.database.mongoose_service import MongooseService

class ConversationTool(ContextPipelineTool):
    
    def __init__(self,configService:ConfigService,mongooseService:MongooseService):
        super().__init__()
        self.configService = configService
        self.mongooseService = mongooseService
    