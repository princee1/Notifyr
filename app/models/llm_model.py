from typing import ClassVar, List, Literal, Optional, Self
from pydantic import BaseModel, Field, field_validator, model_validator
from app.classes.mongo import MongoCondition
from app.classes.profiles import BaseProfileModel, ProfilModelValues
from app.utils.constant import MongooseDBConstant, VaultConstant,LLMProviderConstant

DEFAULT_MAX_TOKENS = 8192
DEFAULT_TEMPERATURE = 1


openai_embedding =  ["text-embedding-ada-002", "text-embedding-3-small", "text-embedding-3-large"]
gemini_embedding =  ['text-embedding-001','gemini-embedding-001','text-embedding-005']

class EmbeddingConfig(BaseModel):
    model:str
    max_retries: int = 10,
    timeout: float = 60

class GraphitiLLMConfig(BaseModel):
    model: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[float] = DEFAULT_TEMPERATURE
    max_tokens: Optional[int] = DEFAULT_MAX_TOKENS
    small_model: Optional[str] = None
    cache:Optional[bool] = False
    reasoning: Optional[Literal['minimal']] = None
    verbosity:Optional[Literal['low']] = None

    @field_validator('temperature')
    def validate_temperature(cls, v):
        if v is not None and not (0 <= v <= 2):
            raise ValueError("Temperature must be between 0 and 2")
        return v

    @field_validator('max_tokens')
    def validate_max_tokens(cls, v):
        if v is not None and v < 1:
            raise ValueError("max_tokens must be a positive integer")
        return v


class GraphitiEmbeddingConfig(BaseModel):
    embedding_model:str
    embedding_dim:Optional[int] = 1024
    base_url:Optional[str] = None
    batch:Optional[int] = Field(default=100,ge=10,le=500)

GRAPHITI_EMBEDDER_PROVIDER_SET = {
                    'openai',
                    # 'gemini',
                    }

class LLMProfileModel(BaseProfileModel):
    
    provider:LLMProviderConstant.LLMProvider
    models:List[str] = []

    embedding_search:EmbeddingConfig
    embedding_parse:EmbeddingConfig

    graph_config: Optional[GraphitiLLMConfig] = None
    graph_embedding_config: Optional[GraphitiEmbeddingConfig] = None
    graph_reranker_config: Optional[GraphitiLLMConfig] =  None

    max_input_tokens:Optional[int] = None
    max_output_tokens:Optional[int] = None

    api_key:str
    api_name:str = 'default'
    api_version:Optional[str]=None
    endpoint:Optional[str] = None

    _secrets_keys:ClassVar[List[str]] = ['api_key']
    _unique_indexes: ClassVar[list[str]] = ['provider','api_name']
    _collection:ClassVar[Optional[str]] = MongooseDBConstant.LLM_COLLECTION
    _vault:ClassVar[str] = VaultConstant.LLM_SECRETS
    _queue:ClassVar[str] = 'llm'

    _condition:ClassVar[Optional[MongoCondition]] = [
        MongoCondition(
            validation='exist',
            force=False,
            filter={'graph_embedding_config':{"$ne":None}},
            method='simple-number-validation',
            rule={"$ge":1}
        ),
        MongoCondition(
            validation='exist',
            force=False,
            filter={'graph_reranker_config':{"$ne":None}},
            method='simple-number-validation',
            rule={"$ge":1}
        ),
        MongoCondition(
            validation='exist',
            force=False,
            filter={'graph_config':{"$ne":None}},
            method='simple-number-validation',
            rule={"$ge":1}
        ),

    ]

    class Settings:
        name=MongooseDBConstant.LLM_COLLECTION

    @field_validator('max_input_tokens','max_output_tokens')
    def token_validation(cls,token):
        if token is not None and token < 0:
            raise ValueError("Token count cannot be negative")
        return token
    
    @model_validator(mode='after')
    def graphiti_validation(self:Self)->Self:
        if self.graph_embedding_config != None and self.provider not in GRAPHITI_EMBEDDER_PROVIDER_SET:
            raise ValueError('We can only use the openai or gemini embedding')

        if self.graph_reranker_config != None and self.provider not in GRAPHITI_EMBEDDER_PROVIDER_SET:
            raise ValueError('We can only use the openai or gemini reranker')
    
    @model_validator(mode='after')
    def models_validation(self:Self)->Self:
        if self.models:
            diff = set(self.models).difference(LLMProviderConstant.MODELS[self.provider])
            if len(diff) > 0:
                raise ValueError(f'Those models: {list(diff)} are not associated with the provider:{self.provider}' )
            
            if self.graph_config != None:
                if self.graph_config.model not in self.models:
                    raise ValueError(f"Graph client config model '{self.graph_config.model}' is not listed in models for provider '{self.provider}'.")

                if self.graph_config.small_model not in self.models:
                    raise ValueError(f"Graph client config small_model '{self.graph_config.small_model}' is not listed in models for provider '{self.provider}'.")
            
            if self.graph_reranker_config != None:
                if self.graph_reranker_config.model not in self.models:
                    raise ValueError(f"Graph reranker config model '{self.graph_reranker_config.model}' is not listed in models for provider '{self.provider}'.")
        return self


    @model_validator(mode='after')
    def reasoning_verbosity_validation(self: Self) -> Self:
        if self.graph_config is not None:
            if self.provider != 'openai':
                if self.graph_config.reasoning is not None:
                    raise ValueError("Reasoning must be None unless provider is 'openai'")
                if self.graph_config.verbosity is not None:
                    raise ValueError("Verbosity must be None unless provider is 'openai'")
        return self

    @model_validator(mode='after')
    def graph_embedding_config_validation(self:Self) -> Self:
        if self.graph_embedding_config != None:
            if self.provider not in GRAPHITI_EMBEDDER_PROVIDER_SET:
                raise ValueError('')

            if self.graph_embedding_config.batch != None and self.provider != 'openai':
                raise ValueError('')
        
        return self


    @model_validator(mode='after')
    def max_tokens_validation(self: Self) -> Self:
        if self.graph_config is not None and self.max_output_tokens is not None:
            if self.graph_config.max_tokens is not None and self.graph_config.max_tokens > self.max_output_tokens:
                self.graph_config.max_tokens = self.max_output_tokens

        if self.graph_reranker_config is not None and self.max_output_tokens is not None:
            if self.graph_reranker_config.max_tokens is not None and self.graph_reranker_config.max_tokens > self.max_output_tokens:
                self.graph_reranker_config.max_tokens = self.max_output_tokens

        return self

ProfilModelValues.update({'llm':LLMProfileModel})