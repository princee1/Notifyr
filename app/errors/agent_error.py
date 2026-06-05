from typing import Iterable
from app.definition._error import BaseError

class AgentToolDoesNotExistError(BaseError):
    
    def __init__(self, id:str,tools:Iterable[str]):
        super().__init__()
        self.id = id
        self.tools = tools


class SemanticAgentAlreadyExistError(BaseError):
    
    def __init__(self,agent_id:str,agent:str,coef:float):
        super().__init__(agent_id,agent)
        self.agent_id = agent_id 
        self.agent = agent
        self.coef = coef

class SemanticToolAlreadyExistError(BaseError):
    ...

class DependencyAgentError(BaseError):
    ...