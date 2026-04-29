from app.definition._tool import ExecutionTool
from app.services import ConfigService
from app.models.agents_model import ToolModel, MCPToolModel

class MCPTool(ExecutionTool):
    
    def __init__(self,configService:ConfigService,config:MCPToolModel):
        super().__init__(config)
        self.configService = configService
        self.config = config

    async def __call__(self,):
        ...
