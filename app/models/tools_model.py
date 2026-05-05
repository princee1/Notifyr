from app.classes.qdrant import QdrantFilterModel, QdrantSearchParamsModel
from pydantic import BaseModel, Field, PrivateAttr, model_validator
from typing import Any, List, Optional, Self, Union

class ToolModel(BaseModel):
    description:str
    name:str

MAX_DISTANCE_SEARCH = 0.7

class QdrantGraphDisperseSearch(BaseModel):
    thresh_add: float = Field(ge=0, le=1)
    thresh_search: float = Field(ge=0, le=1)
    max_context: int = Field(ge=1,le=40)
    max_depth: int = Field(ge=1,le=50)
    branching_factor: int = Field(ge=1,le=100)

    @model_validator(mode='after')
    def validate_threshold(self:Self)->Self:
        if self.thresh_add >= self.thresh_search:
            raise ValueError('The adding threshold should be less than the threshold search because we want to graph search into higher similar chunk')
        
        if self.thresh_search - self.thresh_add > MAX_DISTANCE_SEARCH:
            raise ValueError(f'The disparity between thresh_search and thresh_add is greater than {MAX_DISTANCE_SEARCH} which increase chance of context with bad value')
        return self

class VectorToolModel(ToolModel):
    collection:str
    top_k:int = Field(default=3,ge=1,le=20)
    score_threshold:float = Field(default=0.60,ge=0,le=1)
    search_params:Optional[QdrantSearchParamsModel] = None
    filter:List[QdrantFilterModel] = Field(default_factory=list)
    disperse_search:Optional[QdrantGraphDisperseSearch] = None
    
class CacheToolModel(ToolModel):
    ...

class KnowledgeGraphToolModel(ToolModel):
    ...

class APIToolModel(ToolModel):
    ...

class APIControlModel(APIToolModel):
    ...

class MCPToolModel(ToolModel):
    ...

class SearchToolModel(ToolModel):
    ...

class MemoryToolModel(ToolModel):
    ...

class ConversationToolModel(ToolModel):
    ...


ToolModels = Union[VectorToolModel,CacheToolModel,APIControlModel,APIToolModel,MCPToolModel,SearchToolModel,MemoryToolModel,ConversationToolModel]