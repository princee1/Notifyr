from typing import Any, ClassVar, List, Literal, Optional

from pydantic import BaseModel
from app.classes.profiles import BaseProfileModel,BaseDocument
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

class GenerationConfig(BaseModel):
    temperature: float = 0.7
    timeout:float = 20
    max_retries:int = 5
    max_tokens:Optional[int] = None

    top_p:Optional[float] = None
    top_k:Optional[int] = None
    n:Optional[int] = None
    frequency_penalty:Optional[float] = None
    presence_penalty:Optional[float] = None
    effort:Optional[Effort] = None
    proxy_url:Optional[str] = None    
    reasoning_format: Literal['parsed', 'raw', 'hidden'] | None = None

class ModelProfileConfig(BaseModel):
    image_input:Optional[bool] = False
    image_url_inputs:Optional[bool] = False
    pdf_inputs:Optional[bool] = False
    attachement: Optional[bool] = False

    reasoning_output:Optional[bool] = True
    tool_calling:Optional[bool] = True

    ...
class RateLimiterConfig(BaseModel):
    ...

class AvatarConfig(BaseModel):
    type:Literal['raw','icon','url'] = 'icon'
    value: str

class AgentModel(BaseDocument):
    
    provider: str
    model: str | List[str]
    tools: List[ToolModels] = []
    system:Optional[System] = None
    generation:GenerationConfig = GenerationConfig()
    avatar = Optional[AvatarConfig] = AvatarConfig()
    profile: Optional[ModelProfileConfig] = ModelProfileConfig()
    limit : Optional[RateLimiterConfig] = RateLimiterConfig()

    _collection:ClassVar[str] = MongooseDBConstant.AGENT_COLLECTION

    class Settings:
        name = MongooseDBConstant.AGENT_COLLECTION

AgentValidationModel = subset_model(AgentModel,f'Validation{AgentModel.__class__.__name__}')