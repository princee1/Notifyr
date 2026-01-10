from typing import ClassVar, List, Optional
from openai import BaseModel
from pydantic import field_validator
from typing_extensions import Literal
from app.classes.profiles import BaseProfileModel, ProfilModelValues
from app.utils.constant import MongooseDBConstant, VaultConstant

LLMProvider = Literal['openai','gemini','anthropic','ollama','cohere','groq','deepseek']


class Embedding(BaseModel):
    model:str
    max_retries: int = 10,
    timeout: float = 60
    
class LLMProfileModel(BaseProfileModel):
    
    _collection:ClassVar[Optional[str]] = MongooseDBConstant.LLM_COLLECTION
    _vault:ClassVar[str] = VaultConstant.LLM_SECRETS
    provider:LLMProvider
    models:List[str] = []
    embedding_search:Embedding
    embedding_parse:Embedding
    max__input_tokens:Optional[int] = None
    max_output_tokens:Optional[int] = None
    _queue:ClassVar[str] = 'llm'
    api_key:str
    api_name:str = 'default'
    _secrets_keys:ClassVar[List[str]] = ['api_key']
    _unique_indexes: ClassVar[list[str]] = ['provider','api_name']
    #_unique_indexes: ClassVar[list[str]] = ['provider']

    class Settings:
        name=MongooseDBConstant.LLM_COLLECTION

    @field_validator('max__input_tokens','max_output_tokens',mode='before')
    def token_validation(cls,token):
        if token is not None and token < 0:
            raise ValueError("Token count cannot be negative")
        return token
    

ProfilModelValues.update({'llm':LLMProfileModel})