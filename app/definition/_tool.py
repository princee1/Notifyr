from dataclasses import dataclass, field
from pydantic import BaseModel
from app.models.odm.agents_model import MemoryPolicy
from app.models.tools_model import ToolModel
from langchain.messages import SystemMessage, HumanMessage,ToolMessage
from langchain.agents.middleware import wrap_tool_call,ModelRequest, ModelResponse
from typing import Any, Callable, Dict, Literal, Optional, Set, Type, TypedDict
from app.definition._error import BaseError
from langchain.agents.middleware.types import AgentState

#########################################################################################################
############################                TOOL RUNTIME              ###################################
#########################################################################################################

class NotifyrAgentState(AgentState):
    preferences:Dict[str,Any]
    permission:list[str]
    guest:Optional[Dict]

@dataclass
class NotifyrContext:
    request_id:str
    session_id:str
    channel:str
    user_id:str
    permissions:set[str]
    auth: Literal['guest','subscribed','registered']
    save:bool=True
    user: Optional[dict]  = field(default=None,init=False)

    def __post_init__(self):
        ...
        # NOTE the user will coerce into a schema : base64 -> str -> user_model
    
#########################################################################################################
############################                TOOL DEFINITION           ###################################
#########################################################################################################

class ContextCondition(TypedDict):
    auth:Set[str]
    channel:Set[str]
class Tool:

    Condition: ContextCondition

    def __init__(self,config:ToolModel,memory_policy:MemoryPolicy,store_schema:Type[BaseModel]|None):
        self.config = config
        self.store_schema = store_schema
        self.memory_policy = memory_policy

    @property
    def name(self):
        return self.config.name

    @property
    def description(self):
        return self.config.description

    @property
    def arg_schema(self)->Type[BaseModel]:
        ...
    
class ExecutionTool(Tool):
    ...
class ContextPipelineTool(Tool):
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
