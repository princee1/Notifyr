from app.models.agents_model import ToolModel

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
