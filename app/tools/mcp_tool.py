from app.definition._tool import ReAct
from app.services import ConfigService
class MCPTool(ReAct):
    
    def __init__(self,configService:ConfigService):
        super().__init__()
        self.configService = configService

    async def __call__(self,):
        ...
