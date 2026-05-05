from typing import Any, ClassVar, List, Literal, Optional
from app.classes.mongo import BaseDocument
from app.classes.prompt import System
from app.utils.constant import MongooseDBConstant
from enum import Enum
from app.utils.helper import subset_model

from app.models.tools_model import ToolModels
class GraphitiSearchConfig(str, Enum):
    PERSONALIZED_MEMORY = "personalized_memory"
    PRECISE_QA = "precise_qa"
    CONVERSATION_REASONING = "conversation_reasoning"
    DEFAULT_SEARCH = "default_search"
    RAG_COVERAGE = "rag_coverage"

Effort=Literal['high','medium','low']


class AgentModel(BaseDocument):
    
    _collection:ClassVar[str] = MongooseDBConstant.AGENT_COLLECTION
    
    memory:List[str] = []
    model: str
    tools: List[ToolModels] = []
    system:Optional[System] = None
    
    provider: str
    temperature: float = 0.7
    timeout:float = 20
    max_retries:int = 5
    top_p:Optional[float] = None
    top_k:Optional[int] = None
    n:Optional[int] = None
    frequency_penalty:Optional[float] = None
    presence_penalty:Optional[float] = None
    organisation:Optional[str] =None
    max_tokens:Optional[int] = None
    effort:Optional[Effort] = None
    proxy_url:Optional[str] = None    
    reasoning_format: Literal['parsed', 'raw', 'hidden'] | None = None,

    class Settings:
        name = MongooseDBConstant.AGENT_COLLECTION

AgentValidationModel = subset_model(AgentModel,f'Validation{AgentModel.__class__.__name__}')