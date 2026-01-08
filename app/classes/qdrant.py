from pydantic import BaseModel, Field
from typing import Optional,TypedDict

from app.definition._error import BaseError


class SearchParamsModel(BaseModel):
    hnsw_ef: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of candidates HNSW will explore (higher = better recall)"
    )
    exact: Optional[bool] = Field(
        default=None,
        description="If true, perform exact (brute-force) search"
    )
    indexed_only: Optional[bool] = Field(
        default=None,
        description="Search only indexed vectors"
    )

    def to_qdrant(self) -> dict:
        """Convert to Qdrant-compatible dict, removing None values."""
        return self.model_dump(exclude_none=True)




class TextPayload(TypedDict):
  # Core
  text:str

  # Identity
  document_id:str
  node_id:str
  source:str
  document_type:str #"pdf",

  # Structure
  page:int
  chunk_id:str
  chunk_index:str
  section:str
  content_type:str

  # NLP
  language:str # "en",
  token_count:int  #len(tokens),
  full_token_count:int
  sentence_count: int  #len(list(nlp(text).sents)),
  keywords:list[str]  #extract_keywords(text),
  topics:list[str] #extract_topics(text),
  word_count:int
  most_common:list[str]
  relationship:list[int]

  # Quality
  density:str #density_label(len(tokens)),
  created_at:str #datetime.utcnow().isoformat()

class MultimediaPayload(TypedDict):
  ...

class DataPontsPayload(TypedDict):
    ...


class QdrantCollectionDoesNotExist(BaseError):
    ...