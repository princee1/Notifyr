from typing import Any, ClassVar, List, Literal, Optional, Self, Tuple

from pydantic import BaseModel, Field, field_validator, model_validator
from app.classes.conversation import Channel
from app.classes.embeddings import EmbeddingModel
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

class ModelCallLimitConfig(BaseModel):
    thread_limit:Optional[int] = Field(default=None,ge=100)
    run_limit:Optional[int] = Field(default=None,ge=5)

    @model_validator(mode='after')
    def validate_limit(self):
        if self.thread_limit == None and self.run_limit == None:
            return None
        
        return self

class MessageLimitConfig(BaseModel):
    guest:Optional[int] = Field(None,ge=10,le=100)
    subscribed:Optional[int] = Field(None,ge=100,le=500)
    registered:Optional[int] = Field(None,ge=300,le=600)


#########################################################################################################
############################                                          ###################################
#########################################################################################################



class AgentModel(BaseDocument):
    
    provider: str = Field(description='The service id of the LLM Provider')
    system:System
    model: str | List[str]
    storeModel:Optional[str] = None
    memoryModel:Optional[str] = None
    tools: List[str] = Field(default_factory=list)
    storePolicy: Optional[StoreMemoryPolicy] = None
    dynamicModel:Optional[DynamicModelSelectionConfig] = DynamicModelSelectionConfig()
    trimmer:Optional[TrimmerStrategy] = TrimmerStrategy()
    generation:GenerationConfig = GenerationConfig()
    avatar: Optional[AvatarConfig] = AvatarConfig()
    profile: Optional[ChatProfileConfig] = ChatProfileConfig()
    limiter : Optional[RateLimiterConfig] = RateLimiterConfig()
    callLimit: Optional[ModelCallLimitConfig] = ModelCallLimitConfig()
    messageLimit: Optional[MessageLimitConfig] = MessageLimitConfig()
    throttle:Optional[bool] = False
    interruptChannel:List[Channel] = Field(default_factory=list)
    dynamicPrompt:Optional[bool] = Field(default=True,description='update the system prompt based on context,[NOTE may lose the cache]')

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

    class Settings:
        name = MongooseDBConstant.AGENT_COLLECTION
    
    @field_validator('model',mode='after')
    def _validate_models(cls,m):
        if isinstance(m,list) and len(m) <1:
            raise ValueError('Dynamic model selection agents should have at least 2 model')
        return m

AgentValidationModel = subset_model(AgentModel,f'Validation{AgentModel.__class__.__name__}')