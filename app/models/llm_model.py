from typing import ClassVar, List, Optional, Self
from pydantic import BaseModel, field_validator, model_validator
from app.classes.profiles import BaseProfileModel, ProfilModelValues
from app.utils.constant import MongooseDBConstant, VaultConstant,LLMProviderConstant


class EmbeddingConfig(BaseModel):
    model:str
    max_retries: int = 10,
    timeout: float = 60

class KnowledgeGraphConfig(BaseModel):
    ...
    
class LLMProfileModel(BaseProfileModel):
    
    _collection:ClassVar[Optional[str]] = MongooseDBConstant.LLM_COLLECTION
    _vault:ClassVar[str] = VaultConstant.LLM_SECRETS
    provider:LLMProviderConstant.LLMProvider
    models:List[str] = []
    embedding_search:EmbeddingConfig
    embedding_parse:EmbeddingConfig
    max_input_tokens:Optional[int] = None
    max_output_tokens:Optional[int] = None
    _queue:ClassVar[str] = 'llm'
    api_key:str
    api_name:str = 'default'
    _secrets_keys:ClassVar[List[str]] = ['api_key']
    _unique_indexes: ClassVar[list[str]] = ['provider','api_name']
    #_unique_indexes: ClassVar[list[str]] = ['provider']

    class Settings:
        name=MongooseDBConstant.LLM_COLLECTION

    @field_validator('max_input_tokens','max_output_tokens')
    def token_validation(cls,token):
        if token is not None and token < 0:
            raise ValueError("Token count cannot be negative")
        return token
    
    @model_validator(mode='after')
    def models_validation(self:Self)->Self:
        if self.models:
            diff = set(self.models).difference(LLMProviderConstant.MODELS[self.provider])
            if len(diff) > 0:
                raise ValueError(f'Those models: {list(diff)} are not associated with the provider:{self.provider}' )
        return self
    

ProfilModelValues.update({'llm':LLMProfileModel})