from pydantic import BaseModel
from app.definition._tool import ManagerTool, Tool, ToolContextFactory, ToolRuntime
from app.models.odm.agents_model import StoreMemoryPolicy
from app.models.odm.tools_model import MCPServerToolModel, MCPToolModel
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from langchain_core.tools.base import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient


class MCPManagerTool(ManagerTool):

    def __init__(self,config:MCPServerToolModel,client:MultiServerMCPClient):
        super().__init__(config,)
        self.client = client

    async def __call__(self,runtime:ToolRuntime):
        try:
            async with ToolContextFactory() as factory:
                ...
        except TimeoutError:
            return ...
        except ConnectionError:
            return ...
        except:
            ...
    
    async def load_ressources(self):
        ...
    
    async def load_prompt(self):
        ...

class MCPTool(Tool):
    
    def __init__(self,mcpModel:MCPToolModel,configService:ConfigService,redisService:RedisService, storePolicy: StoreMemoryPolicy, storeSchema: type[BaseModel] | None):
        super().__init__(mcpModel.server,storePolicy,storeSchema)
        self.configService = configService
        self.redisService = redisService
        self.tool:BaseTool = mcpModel.tool
    
    async def __call__(self, runtime:ToolRuntime):
        try:
            async with ToolContextFactory() as factory:
                await self.tool.ainvoke()
        except TimeoutError:
            return ...
        except ConnectionError:
            return ...
