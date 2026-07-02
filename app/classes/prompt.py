from typing import TypedDict

class PromptToken(TypedDict):
    input:int
    output:int
    request_id:str
    issuer:str
    agent:str


from typing import Optional, Literal
from pydantic import BaseModel, Field

class System(BaseModel):
    # Core identity
    persona: str = Field(..., description="Who the agent is")
    task: str = Field(..., description="Primary responsibility")
    # Tone / style
    personality: Literal["professional","friendly","formal","casual","analytical","creative","empathetic","assertive"] = "professional"
    detail: Literal["concise","balanced","precise","comprehensive"] = "balanced"
    audience: Literal["general","beginner","intermediate","expert","executive"] = "general"
    uncertainty_behavior: Literal["say_unknown","best_effort","ask_clarifying_question"] = "say_unknown"
    # Optional custom instruction
    instruction: Optional[str] = None