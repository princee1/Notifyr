from dataclasses import dataclass, field
from pydantic import BaseModel
from app.models.odm.agents_model import StoreMemoryPolicy
from app.models.tools_model import ToolModel
from langchain.messages import SystemMessage, HumanMessage,ToolMessage
from langchain.agents.middleware import wrap_tool_call,ModelRequest, ModelResponse
from typing import Callable, Optional, Set, Type, TypedDict
from app.definition._error import BaseError
from app.definition._agent import NotifyrContext,NotifyrAgentState,ToolType,ToolMetadata
from langchain.tools import ToolRuntime as BaseToolRuntime

#########################################################################################################
############################                                          ###################################
#########################################################################################################

ToolRuntime=BaseToolRuntime[NotifyrContext,NotifyrAgentState]

class ToolArtifact(TypedDict):
    process_time:int
    error:Optional[dict]


#########################################################################################################
############################                TOOL DEFINITION           ###################################
#########################################################################################################

class ContextCondition(TypedDict):
    auth:Set[str]
    channel:Set[str]

class Tool:

    Condition: ContextCondition

    def __init__(self,config:ToolModel,memoryPolicy:StoreMemoryPolicy,storeSchema:Type[BaseModel]|None):
        self.config = config
        self.storeSchema = storeSchema
        self.memoryPolicy = memoryPolicy

    @property
    def name(self):
        return self.config.alias

    @property
    def description(self):
        return self.config.description

    @property
    def arg_schema(self)->Type[BaseModel]:
        ...
    
    @property
    def tool_id(self):
        return self.config.id

    def to_hitl(self):
        if self.config.interrupt_on == None:
            return None
        if isinstance(self.config.interrupt_on,bool):
            return {self.name:self.config.interrupt_on} 
        return {self.name:self.config.interrupt_on.model_dump()}
    
    async def __call__(self,runtime:ToolRuntime):
        ...
    
class ExecutionTool(Tool):
    ...
class RetrievalTool(Tool):
    ...
class ManagerTool(Tool):
    ...
class DiscoveryTool(Tool):
    ...

#########################################################################################################
############################         TOOL ERROR DEFINITION            ###################################
#########################################################################################################
class ToolError(BaseError):
    ...

#########################################################################################################
############################        TOOL MIDDLEWARE                   ###################################
#########################################################################################################

@wrap_tool_call
async def handle_tool_errors(request:ModelRequest,handler:Callable[[ModelRequest], ModelResponse]):
    try:
        return handler(request)
    except:
        return ToolMessage()

@wrap_tool_call
async def dynamic_tool_selection(request: ModelRequest,handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
    tools = []
    request = request.override(tools=tools)
    return handler(request)
