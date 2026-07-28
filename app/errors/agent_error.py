from typing import Iterable
from app.definition._error import BaseError
from app.definition._service import ServiceStatus

class AgentToolDoesNotExistError(BaseError):
    
    def __init__(self, id:str,tools:Iterable[str]):
        super().__init__()
        self.id = id
        self.tools = tools

class AgenticRemoteCallError(BaseError):
    ...

class AgentOnlyAsSubAgentError(BaseError):
    def __init__(self, agentId):
        super().__init__(agentId)
        self.agentId = agentId

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

class AgentNotAvailableError(BaseError):
    def __init__(self,status:ServiceStatus,reason:str,who:str=None):
        self.status = status
        self.reason = reason
        self.who = who
