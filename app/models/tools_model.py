from app.classes.qdrant import QdrantSearchParamsModel
from pydantic import BaseModel, Field, PrivateAttr
from typing import Any, List, Optional, Union

class ToolModel(BaseModel):
    description:str
    name:str

class QdrantGraphSparseSearch(BaseModel):
    thresh_add:float
    thresh_search:float
    max_context:int
    max_depth:int
    branching_factor:int

class VectorToolModel(ToolModel):
    collection:str
    top_k:int = Field(default=3,ge=1,le=20)
    score_threshold:float = Field(default=0.60,ge=0,le=1)
    search_params:Optional[QdrantSearchParamsModel] = None
    filter:List[Any] = Field(default_factory=list)
    sparse_search:Optional[QdrantGraphSparseSearch] = None
    
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