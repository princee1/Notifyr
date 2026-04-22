from app.definition._tool import Tool
from app.services.config_service import ConfigService
from app.services.database.graphiti_service import GraphitiService

class MemoryTool(Tool):
    
    def __init__(self,configService:ConfigService,graphitiService:GraphitiService):
        super().__init__()
        self.configService = configService
        self.graphitiService = graphitiService
    
    async def __call__(self,query:str ):
        ...