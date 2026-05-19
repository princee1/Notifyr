from app.models.tools_model import ToolModel
from langchain.messages import SystemMessage, HumanMessage,ToolMessage
from langchain.agents.middleware import wrap_tool_call,ModelRequest, ModelResponse
from typing import Callable

class Tool:
    def __init__(self,config:ToolModel):
        self.config = config

    @property
    def name(self):
        return self.config.name

    @property
    def description(self):
        return self.config.description

class ExecutionTool(Tool):
    ...
class ContextPipelineTool(Tool):
    ...
class DiscoveryTool(Tool):
    ...

@wrap_tool_call
async def handle_tool_errors(request:ModelRequest,handler:Callable[[ModelRequest], ModelResponse]):
    try:
        return await handler(request)
    except:
        return ToolMessage()

@wrap_tool_call
async def dynamic_tool_selection(request: ModelRequest,handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
    tools = []
    request = request.override(tools=tools)
    return await handler(request)
