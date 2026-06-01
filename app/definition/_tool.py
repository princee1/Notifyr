from dataclasses import dataclass, field
from pydantic import BaseModel
from app.models.odm.agents_model import StoreMemoryPolicy
from app.models.tools_model import ContextCondition, ToolModel
from langchain.messages import SystemMessage, HumanMessage,ToolMessage
from langchain.agents.middleware import ToolCallLimitMiddleware, wrap_tool_call,ModelRequest, ModelResponse
from typing import Callable, Optional, Set, Type, TypedDict
from app.definition._error import BaseError
from app.definition._agent import NotifyrContext,NotifyrAgentState,ToolClass,ToolMetadata,BaseToolArtifact
from langchain.tools import ToolRuntime as BaseToolRuntime

#########################################################################################################
############################                                          ###################################
#########################################################################################################

ToolRuntime=BaseToolRuntime[NotifyrContext,NotifyrAgentState]

#########################################################################################################
############################                TOOL DEFINITION           ###################################
#########################################################################################################


class Tool:

    Condition: ContextCondition = None

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

    def to_condition(self):
        return [self.Condition,self.config.condition]

    def to_limit(self)->None | ToolCallLimitMiddleware:
        if self.config.limit == None:
            return None
        return ToolCallLimitMiddleware(tool_name=self.name,
                                       thread_limit=self.config.limit.thread,
                                       run_limit=self.config.limit.run)

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
async def handle_tool_errors(request:ModelRequest[NotifyrContext],handler:Callable[[ModelRequest[NotifyrContext]], ModelResponse]):
    try:
        return await handler(request)
    except:
        return ToolMessage()


@wrap_tool_call
async def dynamic_tool_selection(request: ModelRequest[NotifyrContext],handler: Callable[[ModelRequest[NotifyrContext]], ModelResponse]) -> ModelResponse:

    context = request.runtime.context
    filtered_tools = []
    for t in request.tools:
        condition:ContextCondition

        for condition in t.extras.get('__condition__',[]):
            if condition == None:
                filtered_tools.append(t)

            if condition.as_is == None:
                filtered_tools.append(t)
            
            if condition.verify(context.auth,context.channel,context.user):
                filtered_tools.append(t)
        
    request = request.override(tools=filtered_tools)
    return await handler(request)

