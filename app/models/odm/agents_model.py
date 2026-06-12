import math
from typing import Any, ClassVar, Dict, List, Literal, Optional, Self, Tuple

from pydantic import BaseModel, Field, PrivateAttr, field_validator, model_validator
from app.classes.conversation import Auth, Channel
from app.classes.embeddings import EmbeddingModel
from app.classes.profiles import BaseProfileModel,BaseDocument
from app.classes.prompt import System
from app.utils.constant import MongooseDBConstant
from enum import Enum
from app.utils.helper import subset_model

class GraphitiSearchConfig(str, Enum):
    PERSONALIZED_MEMORY = "personalized_memory"
    PRECISE_QA = "precise_qa"
    CONVERSATION_REASONING = "conversation_reasoning"
    DEFAULT_SEARCH = "default_search"
    RAG_COVERAGE = "rag_coverage"

Effort=Literal['high','medium','low']
MIN_OF_MAX_INPUT_TOKEN = 40_000

class GenerationConfig(BaseModel):
    temperature: float = 0.7
    timeout:float = 20
    max_retries:int = 5
    max_tokens:Optional[int] = Field(None, ge=4000)

    top_p:Optional[float] = None
    top_k:Optional[int] = None
    n:Optional[int] = None
    frequency_penalty:Optional[float] = None
    presence_penalty:Optional[float] = None
    effort:Optional[Effort] = None
    proxy_url:Optional[str] = None    
    reasoning_format: Literal['parsed', 'raw', 'hidden'] | None = None

class ChatProfileConfig(BaseModel):
    image_input:Optional[bool] = False
    image_url_inputs:Optional[bool] = False
    pdf_inputs:Optional[bool] = False
    attachement: Optional[bool] = False

    reasoning_output:Optional[bool] = True
    tool_calling:Optional[bool] = True
    max_inputs_token:Optional[int] = Field(None, ge=MIN_OF_MAX_INPUT_TOKEN)
    
class RateLimiterConfig(BaseModel):
    ...

class AvatarConfig(BaseModel):
    type:Literal['raw','icon','url'] = 'icon'
    value: str = ''

class StoreMemoryPolicy(BaseModel):
    allowed_types: list[str]
    namespace: str
    ttl: Optional[int]
    visibility: Literal["agent", "user", "global"]

class TrimmerStrategy(BaseModel):
    mode:Literal['summarize','trim'] ='trim'
    keep_message:int = Field(100,ge=25,le=300)
    tokens_trigger: int = Field(MIN_OF_MAX_INPUT_TOKEN*0.80,ge=MIN_OF_MAX_INPUT_TOKEN*.60)
    keep_referenced_tools:Optional[bool] = Field(default=False,description='Whether we should add ToolMessage that are depend on by later AIMessage')

class DynamicModelSelectionConfig(BaseModel):
    mode:Literal['optimization','fallback','both'] = 'both'
    baseChatIndex:Optional[int] = None
    summaryChatIndex:Optional[int] = None
    interruptChatIndex:Optional[int] = None
    reverse:Optional[bool] = Field(default=False,description='[F] the more complex the more higher the model (Fallback: [H->L]) [T]: The more complex the lower model (Fallback [L->H])')
    trigger_message:Optional[int] = Field(default=None,ge=50)

    @property
    def _reverse(self):
        if self.reverse:
            return 1
        return -1

class ModelCallGuardConfig(BaseModel):
    thread_limit:Optional[int] = Field(default=None,ge=100)
    run_limit:Optional[int] = Field(default=None,ge=5)
    max_retries=Optional[int] = Field(default=None,ge=2,le=10)
    max_delay:Optional[int] = Field(default=None,ge=60,le=280)

    _limit:bool = PrivateAttr(default=True)
    _retry:bool = PrivateAttr(default=True)

    limit_keys:ClassVar[tuple[str,...]] = ('thread_limit','run_limit')
    retry_keys:ClassVar[tuple[str,...]] = ('max_retries','max_delay')


    @model_validator(mode='after')
    def validate_limit(self):
        if self.thread_limit == None and self.run_limit == None:
            self._limit=False

        if self.max_retries == None and self.max_delay == None:
            self._retry = False

        if not self._limit and not self._retry:
            return None
        
        return self


def LimitConfigFactory(factor:int):
    class LimitConfig(BaseModel):
        
        guest:Optional[int] = Field(None,ge=1*factor,le=10*factor)
        subscribed:Optional[int] = Field(None,ge=10*factor,le=50*factor)
        registered:Optional[int] = Field(None,ge=30*factor,le=60*factor)

    return LimitConfig


class ThreadMessageLimitConfig(LimitConfigFactory(5)):
    """ """
class SessionMessageLimitConfig(LimitConfigFactory(2)):
    """ """
class SessionCountLimitConfig(LimitConfigFactory(1)):
    """ """

class MessageLimitConfig(BaseModel):
    thread:ThreadMessageLimitConfig = ThreadMessageLimitConfig()
    session:SessionMessageLimitConfig = SessionMessageLimitConfig()
    sessionCount:SessionCountLimitConfig = SessionCountLimitConfig()


class MessageMarkerLimitConfig(BaseModel):
    ai:float|int = Field(default=math.inf,allow_inf_nan=True,ge=100)
    human:int|float = Field(default=math.inf,allow_inf_nan=True,ge=100)

class AuthMarkerFactorConfig(BaseModel):
    guest:int = Field(default=1,ge=1,le=10)
    subscribed:int =Field(default=1,ge=1,le=7)
    registered:int = Field(default=1,ge=1,le=5)

class ToolMarkerLimitConfig(BaseModel):
    execution:int = Field(default=40,ge=40,allow_inf_nan=True)
    error:int = Field(default=30,ge=30,allow_inf_nan=True)
    manager:int = Field(default=20,ge=20,allow_inf_nan=True)
    
class MarkerConfig(BaseModel):
    tool:ToolMarkerLimitConfig = Field(default_factory=ToolMarkerLimitConfig)
    message:MessageMarkerLimitConfig = Field(default_factory=MessageMarkerLimitConfig)
    factor:AuthMarkerFactorConfig = Field(default_factory=AuthMarkerFactorConfig)
    
#########################################################################################################
############################                                          ###################################
#########################################################################################################


class AgentModel(BaseDocument):
    
    system:System
    model: str | List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    type:Literal['main-agent','sub-agent'] = Field(default='main-agent')
    rag:Literal['agentic','linear','hybrid','auto'] = Field(default='agentic')
    cache:Literal['agentic','linear'] = Field(default='agentic')
    provider: str = Field(description='The service id of the LLM Provider')

    interruptChannel:List[Channel] = Field(default_factory=list)
    dynamicPrompt:Optional[bool] = Field(default=True,description='update the system prompt based on context,[NOTE may lose the cache]')

    storeModel:Optional[str] = None
    memoryModel:Optional[str] = None

    throttle:bool = Field(default=False)
    avatar: AvatarConfig = Field(default_factory=AvatarConfig)
    generation:GenerationConfig = Field(default_factory=GenerationConfig)
    profile: ChatProfileConfig = Field(default_factory=ChatProfileConfig)
    marker: MarkerConfig = Field(default_factory=MarkerConfig)

    limiter : Optional[RateLimiterConfig] = Field(default_factory=RateLimiterConfig)
    callGuard: Optional[ModelCallGuardConfig] = Field(default_factory=ModelCallGuardConfig)
    messageLimit: Optional[MessageLimitConfig] = Field(default_factory=MessageLimitConfig)
    dynamicModel:Optional[DynamicModelSelectionConfig] = Field(default_factory=DynamicModelSelectionConfig)
    trimmer:Optional[TrimmerStrategy] = Field(default_factory=TrimmerStrategy)
    
    storePolicy: Optional[StoreMemoryPolicy] = None
    embeddings:Optional[EmbeddingModel] = None

    _collection:ClassVar[str] = MongooseDBConstant.AGENT_COLLECTION


    @field_validator('interruptChannel',mode='after')
    def ensure_interrupt_channel(cls,v):
        return list(set(v))

    @field_validator('profile','avatar',mode='after')
    def ensure_not_none(cls,v):
        if v == None:
            raise ValueError('Cannot be forced None')
        return v

    @field_validator('model',mode='after')
    def validate_list_model(cls,m:list[str]|str):
        if isinstance(m,str):
            return m
        if len(m) == 0:
            raise ValueError('You must provide at least one model')
        if len(m) == 1:
            return m[0]
        return m

    @property
    def _model(self):
        if isinstance(self.model,str):
            return [self.model]
        return self.model

    @model_validator(mode='after')
    def _validate_agent(self:Self)->Self:
        if self.dynamicModel != None:
            if isinstance(self.model,str):
                raise ValueError('Dynamic model only works with a list model')
            if isinstance(self.model,list) and len(self.model)<=1:
                raise ValueError('Dynamic model only works with a list model with at least 2 model')
        else:
            if isinstance(self.model,list) and len(self.model) >=2:
                raise ValueError('')

        if self.trimmer and self.profile.max_inputs_token != None:
            if self.trimmer.tokens_trigger >= self.profile.max_inputs_token*0.95:
                raise ValueError('Token trigger cant be higher than 95% of the max_input_token')

        # if self.trimmer != None and isinstance(self.model,list):
        #     if self.trimmer.mode == 'summarize' and len(self.model)>=2:
        #         raise ValueError('Cannot summarize with only one model because the goal is to summarize with a simpler model')

        return self

    @field_validator('model',mode='after')
    def _validate_models(cls,m):
        if isinstance(m,list) and len(m) <1:
            raise ValueError('Dynamic model selection agents should have at least 2 model')
        return m
    
    @field_validator('embeddings',mode='before')
    def ensure_no_embedding(cls,e):
        return None

    class Settings:
        name = MongooseDBConstant.AGENT_COLLECTION

AgentValidationModel = subset_model(AgentModel,f'Validation{AgentModel.__class__.__name__}')