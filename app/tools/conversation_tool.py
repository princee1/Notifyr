from app.definition._tool import RetrievalTool, ManagerTool,ToolRuntime as ToolRuntime
from app.services.config_service import ConfigService
from app.services.database.mongoose_service import MongooseService
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.types import Command
from langchain.messages import ToolMessage
from langchain.tools import  tool



class ConversationTool(ManagerTool):
    
    def __init__(self,configService:ConfigService,mongooseService:MongooseService,checkpointer:MongoDBSaver):
        super().__init__()
        self.configService = configService
        self.mongooseService = mongooseService
        self.checkpointer = checkpointer

    # it changes the preferences
    # it ask permission for the thread/ns 
    # it learns about a guest by asking question
    # it can changes 
    # it can fetch other conversation
    # fetch data in the store
    async def __call__(self, runtime:ToolRuntime):
        ...
