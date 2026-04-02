from typing import ClassVar, List, Literal, Optional, Self
from pydantic import BaseModel, Field, field_validator, model_validator
from app.classes.mongo import MongoCondition
from app.classes.profiles import BaseProfileModel, ProfilModelValues
from app.utils.constant import MongooseDBConstant, VaultConstant,LLMProviderConstant
from app.utils.helper import subset_model

DEFAULT_MAX_TOKENS = 8192
DEFAULT_TEMPERATURE = 1

class BaseTemperatureMaxTokenModel(BaseModel):
    base_url: Optional[str] = None
    temperature: float | None = None
    max_tokens: int | None = None

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


openai_embedding = [
    "text-embedding-ada-002",
    "text-embedding-3-small",
    "text-embedding-3-large"
]

gemini_embedding = [
    "models/embedding-001",
    "text-embedding-001",
    "gemini-embedding-001",
    "embedding-001",
    "models/text-embedding-004",
    "text-embedding-004",
    "models/text-embedding-005",
    "text-embedding-005"
]

VALID_EMBEDDING_MODELS = {
    'openai': openai_embedding,
    'gemini': gemini_embedding,
}

class VectorEmbeddingConfig(BaseModel):
    model:str
    max_retries: int = 10
    timeout: float = 60
    base_url: str | None = None
    api_version: str | None = None
    batch_size: int = Field(default=100, ge=10, le=500)


class CrawlLLMConfigModel(BaseTemperatureMaxTokenModel):
    model: Optional[str] = None
    top_p: float | None = None,
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stop: List[str] | None = None
    n: int | None = None

class WebResearchConfigModel(BaseTemperatureMaxTokenModel):
    embedding_model:Optional[str] = None
    
class GraphitiLLMConfig(BaseTemperatureMaxTokenModel):
    model: Optional[str] = None
    temperature: Optional[float] = DEFAULT_TEMPERATURE
    max_tokens: Optional[int] = DEFAULT_MAX_TOKENS
    small_model: Optional[str] = None
    cache:Optional[bool] = False
    reasoning: Optional[Literal['minimal']] = None
    verbosity:Optional[Literal['low']] = None

class GraphitiEmbeddingConfig(BaseModel):
    embedding_model:str
    embedding_dim:Optional[int] = 1024
    base_url:Optional[str] = None
    batch:Optional[int] = Field(default=100,ge=10,le=500)

EMBEDDER_PROVIDER_SET = {
                    'openai',
                    'gemini',
                    }

class LLMProfileModel(BaseProfileModel):
    
    provider:LLMProviderConstant.LLMProvider
    models:List[str] = []

    vector_embedding_config:Optional[VectorEmbeddingConfig] = None

    graph_config: Optional[GraphitiLLMConfig] = None
    graph_embedding_config: Optional[GraphitiEmbeddingConfig] = None
    graph_reranker_config: Optional[GraphitiLLMConfig] =  None

    crawl_config: Optional[CrawlLLMConfigModel] = None

    research_config: Optional[WebResearchConfigModel] = None

    max_input_tokens:Optional[int] = None
    max_output_tokens:Optional[int] = None

    api_key:str
    api_name:str = 'default'
    api_version:Optional[str]=None
    base_url:Optional[str] = None
    default_model:Optional[str] = None

    _secrets_keys:ClassVar[List[str]] = ['api_key']
    _unique_indexes: ClassVar[list[str]] = ['provider','api_name']
    _collection:ClassVar[Optional[str]] = MongooseDBConstant.LLM_COLLECTION
    _vault:ClassVar[str] = VaultConstant.LLM_SECRETS
    _queue:ClassVar[str] = 'llm'

    _condition:ClassVar[Optional[MongoCondition]] = [
        MongoCondition(
            validation='exist',
            force=False,
            filter={'vector_embedding_config':{"$ne":None}},
            method='simple-number-validation',
            rule={"$ge":1}
        ), 
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
        MongoCondition(
            validation='exist',
            force=False,
            filter={'graph_config':{"$ne":None}},
            method='simple-number-validation',
            rule={"$ge":1}
        ),
        MongoCondition(
            validation='exist',
            force=False,
            filter={'crawl_config':{"$ne":None}},
            method='simple-number-validation',
            rule={"$ge":1}
        ),
        MongoCondition(
            validation='exist',
            force=False,
            filter={'research_config':{"$ne":None}},
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
    def models_validation(self: Self) -> Self:
        # Validate base models
        if self.models:
            diff = set(self.models).difference(LLMProviderConstant.MODELS[self.provider]['models'])
            if len(diff) > 0:
                raise ValueError(f'Those models: {list(diff)} are not associated with the provider:{self.provider}')
            
            # Validate config models against available models list
            config_validations = [
                (self.graph_config, 'Graph client config', [('model', 'model'), ('small_model', 'small_model')]),
                (self.graph_reranker_config, 'Graph reranker config', [('model', 'model')]),
                (self.crawl_config, 'Crawl config', [('model', 'model')]),
            ]
            
            for config, config_name, model_fields in config_validations:
                if config is not None:
                    for field_name, attr_name in model_fields:
                        model_value = getattr(config, attr_name, None)
                        if model_value and model_value not in self.models:
                            raise ValueError(f"{config_name} {field_name} '{model_value}' is not listed in models for provider '{self.provider}'.")
        
        # Validate embedding configs
        valid_embedding_models = VALID_EMBEDDING_MODELS.get(self.provider, [])
        if self.vector_embedding_config or self.graph_embedding_config or self.research_config:
            if not valid_embedding_models:
                raise ValueError(f"Provider '{self.provider}' does not support embeddings.")
        
        embedding_validations = [
            (self.vector_embedding_config, 'model', 'Vector embedding'),
            (self.graph_embedding_config, 'embedding_model', 'Graph embedding'),
            (self.research_config, 'embedding_model', 'Research embedding'),
        ]
        
        for config, field_name, config_type in embedding_validations:
            if config is not None:
                model_value = getattr(config, field_name, None)
                if model_value and model_value not in valid_embedding_models:
                    raise ValueError(f"{config_type} model '{model_value}' is not valid for provider '{self.provider}'. Valid models: {valid_embedding_models}")

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
    def max_tokens_validation(self: Self) -> Self:
        if self.max_output_tokens is None:
            return self
        
        # Apply max_output_tokens cap to all configs that have max_tokens
        for config in [self.graph_config, self.graph_reranker_config, self.crawl_config, self.research_config]:
            if config is not None and config.max_tokens is not None and config.max_tokens > self.max_output_tokens:
                config.max_tokens = self.max_output_tokens

        return self

    @model_validator(mode='after')
    def default_model_validation(self:Self)->Self:
        
        if not self.default_model:
            if self.provider not in LLMProviderConstant.MODELS:
                raise ValueError(f"Provider '{self.provider}' does not support default model selection.")

            self.default_model = LLMProviderConstant.MODELS[self.provider]['models']

        return self

ProfilModelValues.update({'llm':LLMProfileModel})

LLMProviderValidationModel = subset_model(LLMProfileModel,'LLMProviderValidationModel')