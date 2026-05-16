from app.classes.qdrant import QdrantFilterModel, QdrantSearchParamsModel
from pydantic import BaseModel, Field, PrivateAttr, field_validator, model_validator
from typing import Any, List, Literal, Optional, Self, Union

from app.classes.url import URLMappingModel


####################################################################################################################################
##################################################                                                 #################################
####################################################################################################################################

class ToolModel(BaseModel):
    description:str
    name:str

MAX_DISTANCE_SEARCH = 0.7


####################################################################################################################################
##################################################                                                 #################################
####################################################################################################################################

class BroadRerankerSearchConfig(BaseModel):
    thresh_add: float = Field(ge=0, le=1)
    thresh_search: float = Field(ge=0, le=1)
    max_context: int = Field(ge=1,le=40)
    max_depth: int = Field(ge=1,le=50)
    branching_factor: int = Field(default=5,ge=1,le=100)
    top_k:int = Field(default=3,ge=1,le=20)

    @model_validator(mode='after')
    def top_k_validator(self:Self)->Self:
        if self.top_k > self.max_context:
            raise ValueError('Top K reranked context cannot be higher than the max_context')
        return self

    _skip:bool = PrivateAttr(default=False)

class BaseContextRetrievalToolModel(ToolModel):
    top_k:int = Field(default=3,ge=1,le=20)
    score_threshold:float = Field(default=0.60,ge=0,le=1)
    broad_search:Optional[BroadRerankerSearchConfig] = None

class VectorToolModel(BaseContextRetrievalToolModel):
    collection:str
    search_params:Optional[QdrantSearchParamsModel] = None
    filter:List[QdrantFilterModel] = Field(default_factory=list)
    
    @field_validator('broad_search',mode='after')
    def validate_threshold(cls,v:BroadRerankerSearchConfig)->BroadRerankerSearchConfig:
        if v == None:
            return v
        if v.thresh_add >= v.thresh_search:
            raise ValueError('The adding threshold should be less than the threshold search because we want to graph search into higher similar chunk')
        
        if v.thresh_search - v.thresh_add > MAX_DISTANCE_SEARCH:
            raise ValueError(f'The disparity between thresh_search and thresh_add is greater than {MAX_DISTANCE_SEARCH} which increase chance of context with bad value')
        return v

class MemoryToolModel(BaseContextRetrievalToolModel,):
    include_entity_summary:Optional[bool] = True
    entities:Optional[list[str]] = []
    edges:Optional[list[str]] = []

class KnowledgeGraphToolModel(MemoryToolModel):
    domain:str

####################################################################################################################################
##################################################                                                 #################################
####################################################################################################################################

class APIToolModel(ToolModel):
    url: URLMappingModel
    outbound:str
    body:Optional[str] = None
    res:Optional[str] = None
    res_format:Literal['json','text']='json'

    @model_validator(mode='after')
    def validate_format(self)->Self:
        if self.res and self.res_format == 'text':
            raise ValueError("We cannot parse into a custom model if the format is 'text'")
        return self

class APIControlModel(APIToolModel):
    ...

class MCPToolModel(ToolModel):
    ...


####################################################################################################################################
##################################################                                                 #################################
####################################################################################################################################

class CacheToolModel(ToolModel):
    ...

class SearchToolModel(ToolModel):
    ...

class ConversationToolModel(ToolModel):
    ...

ToolModels = Union[VectorToolModel,CacheToolModel,APIControlModel,APIToolModel,MCPToolModel,SearchToolModel,MemoryToolModel,ConversationToolModel]