from typing import Annotated, Callable
from app.definition._agent import ToolMetadata
from app.definition._tool import ExecutionTool, Tool,ToolRuntime
from langgraph.graph.state import Command, CompiledStateGraph as GraphAgent
from langchain.messages import HumanMessage, ToolMessage
from app.models.odm.agents_model import AgentModel
from langchain.tools import InjectedToolCallId
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse

from app.services.database.qdrant_service import QdrantService
from app.services.database.redis_service import RedisService

class AgentTool(ExecutionTool):
    
    @classmethod
    def to_metadata(cls,subclass:str):
        return Tool.to_metadata('agent', subclass)

class SubAgentTool(AgentTool):

    def __init__(self, config, memoryPolicy, storeSchema,agent:GraphAgent,agentModel:AgentModel):
        super().__init__(config, memoryPolicy, storeSchema)
        self.agent = agent
        self.agentModel = agentModel
    
    async def __call__(self,query:str, runtime:ToolRuntime,tool_call_id: Annotated[str, InjectedToolCallId]):
        query = HumanMessage(query)
        result = await self.agent.ainvoke(query,runtime.context)
        content = result["messages"][-1].content
        return ToolMessage()

class HandoffAgentTool(AgentTool):
    
    def __init__(self, config, memoryPolicy, storeSchema):
        super().__init__(config, memoryPolicy, storeSchema)

    async def __call__(self,current_step:str,content:str,memory:dict,runtime:ToolRuntime)->Command:
        return  Command(update={
            'messages':[ToolMessage(
                content=content,
            )],
            'memory':memory,
            'current_step':current_step,
        })

    @property
    def arg_schema(self):
        return 

    @wrap_model_call
    async def apply_step_config(self,request: ModelRequest,handler: Callable[[ModelRequest], ModelResponse],):
        return await handler(request)

class RouterAgentTool(AgentTool):
    
    def __init__(self, config, memoryPolicy, storeSchema,qdrantService:QdrantService,redisService:RedisService):
        super().__init__(config, memoryPolicy, storeSchema)
        self.qdrantService = qdrantService
        self.redisService = redisService

    
    async def classify_query(self):
        ...