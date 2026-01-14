from typing import ClassVar, List, Literal, Optional
from pydantic import BaseModel
from app.classes.mongo import BaseDocument
from app.utils.constant import LLMProviderConstant, MongooseDBConstant

Effort=Literal['high','medium','low']

class ToolModel(BaseDocument):
    ...

class System(BaseModel):
    persona:str
    behaviors:list[str] = []
    task:str 


class AgentModel(BaseDocument):
    
    _collection:ClassVar[str] = MongooseDBConstant.AGENT_COLLECTION 

    provider: LLMProviderConstant.LLMProvider
    memory:List[str] = []
    model: str
    tools: list[str] = []
    temperature: float = 0.7
    timeout:float = 20
    max_retries:int = 5
    top_p:Optional[float] = None
    top_k:Optional[int] = None
    n:Optional[int] = None
    system:Optional[System] = None
    frequency_penalty:Optional[float] = None
    presence_penalty:Optional[float] = None
    organisation:Optional[str] =None
    max_tokens:Optional[int] = None
    effort:Optional[Effort] = None
    proxy_url:Optional[str] = None    
    reasoning_format: Literal['parsed', 'raw', 'hidden'] | None = None,

    class Settings:
        name = MongooseDBConstant.AGENT_COLLECTION