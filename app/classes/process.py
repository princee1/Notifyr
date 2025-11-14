from typing import TypedDict

class ProcessTerminateProtocol(TypedDict):
    exit_code: int
    reason: str
    instance_id_requestor: str
    
    