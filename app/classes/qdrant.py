from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Self, TypedDict, Literal, Union
from app.classes.chunk import Density, DocumentType, Extension
from app.definition._error import BaseError

class QdrantSearchParamsModel(BaseModel):
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

class TextFieldMatch(BaseModel):
    """Flexible text field matching with strategy selection.
    
    Allows specifying how to match text values:
    - exact: Exact full value match (MatchValue) - fastest, most precise
    - phrase: Full phrase substring match (MatchPhrase) - phrase must exist somewhere in the text
    - token: At least one token match (MatchTextAny) - any word from the search term matches
    """
    value: str = Field(..., description="The text value to match")
    strategy: Literal['phrase', 'token'] = Field(default='phrase',description="How to match: 'phrase' (substring), 'token' (any word)")

class QdrantChunkFilterCondition(BaseModel):
    """Simple filter condition for ChunkPayload fields.
    
    Set only the field you want to filter on. Amateurs can easily understand:
    - Literal fields (extension, language, document_type): provide exact string value
    - List fields (keywords, topics): provide list of strings to match any of them
    - String fields (document_name, document_id, source, title, section): flexible matching
      * Pass a string for exact match: "my_doc.pdf"
      * Pass object with strategy: {"value": "my_doc", "strategy": "phrase"} for substring
    - Text field (text): flexible matching with same options as string fields
    """
    
    # Literal type fields (exact match only)
    extension: Optional[List[Extension]] = Field(default=None,description="Filter by file extension (pdf, docx, md, html, pptx, txt, xml)")
    language: Optional[List[str]] = Field(default=None,description="Filter by language code (e.g., 'en', 'fr', 'es')")
    document_type: Optional[List[DocumentType]] = Field(default=None,description="Filter by document type (textfile, webpage)")
    density: Optional[List[Density]] = Field(default=None,description="Filter by text density")

    # List fields (match any of the values)
    keywords: Optional[list[str]] = Field(default=None,description="Filter by keywords - matches documents containing ANY of these keywords")
    topics: Optional[list[str]] = Field(default=None,description="Filter by topics - matches documents containing ANY of these topics")
    
    # String fields with flexible matching
    document_name: Optional[Union[str, TextFieldMatch]] = Field(default=None,description="Filter by document name. String for exact, dict for flexible matching: {'value': 'text', 'strategy': 'exact|phrase|token'}")
    document_id: Optional[Union[str, TextFieldMatch]] = Field(default=None,description="Filter by document ID. String for exact, dict for flexible matching")
    source: Optional[Union[str, TextFieldMatch]] = Field(default=None,description="Filter by source. String for exact, dict for flexible matching")
    title: Optional[Union[str, TextFieldMatch]] = Field(default=None,description="Filter by title. String for exact, dict for flexible matching")
    section: Optional[Union[str, TextFieldMatch]] = Field(default=None,description="Filter by section. String for exact, dict for flexible matching")
    text: Optional[Union[str, TextFieldMatch]] = Field(default=None,description="Filter by text content. String for exact, dict for flexible matching: {'value': 'text', 'strategy': 'exact|phrase|token'}")
    
    @field_validator('keywords', 'topics', mode='before')
    def ensure_list(cls, v):
        """Ensure list fields are actually lists."""
        if v is not None and not isinstance(v, list):
            return [v]
        return v

    @field_validator('extension', 'language','document_type','density',mode='after')
    def ensure_set_list(cls,v):
        return list(set(v))
        
    @field_validator('document_name', 'document_id', 'source', 'title', 'section', 'text', mode='before')
    def convert_string_to_text_match(cls, v):
        """Convert string values to TextFieldMatch objects with default 'exact' strategy."""
        if v is not None and isinstance(v, str):
            return TextFieldMatch(value=v, strategy='exact')
        return v
    
    def has_filters(self) -> bool:
        """Check if any filter is set."""
        return any(getattr(self, field) is not None for field in self.model_fields.keys())

class QdrantFilterModel(BaseModel):
    """Simplified Qdrant filter model for easy use in FastAPI.
    
    Use like:
    - must: conditions that ALL must match (AND logic)
    - must_not: conditions that NONE should match (NOT logic)
    - should: conditions where AT LEAST ONE should match (OR logic)
    - min_should: minimum number of 'should' conditions that must match
    
    Example usage in FastAPI:
    {
        "must": [
            {"extension": "pdf"},
            {"document_name": "report.pdf"}
        ],
        "should": [
            {"keywords": ["important", "urgent"]},
            {"topics": ["finance"]}
        ]
    }
    """
    
    must: Optional[QdrantChunkFilterCondition] = Field(default=None,description="All these conditions must match (AND logic)")
    must_not: Optional[QdrantChunkFilterCondition] = Field(default=None,description="None of these conditions should match (NOT logic)")
    should: Optional[QdrantChunkFilterCondition] = Field(default=None,description="At least one of these conditions should match (OR logic)")
    min_should: Optional[int] = Field(default=1,ge=1,description="Minimum number of 'should' conditions that must match. If not set, at least 1 will match")
    
    def is_empty(self) -> bool:
        """Check if filter has any conditions."""
        return not any([self.must, self.must_not, self.should])


    @field_validator('must',mode='after')
    def validate_must(cls,v:QdrantChunkFilterCondition):
        if v == None:
            return v
        for field,value in v.model_dump(include=('must',)):
            if field not in LITERAL_FIELDS:
                continue
            if value and len(value) > 1:
                raise ValueError(f'When in a must the list of {field} exact match should always be 1')
        
        return v
    
    @model_validator(mode='after')
    def validate_whole_filter(self:Self):
        if self.is_empty():
            raise ValueError('At least one type of condition must be set')
        return self

FLEXIBLE_TEXT_FIELDS = {'document_name', 'document_id','source','title', 'section','text'}
LITERAL_FIELDS = {'extension','language','document_type','density'}
LIST_FIELDS = {'keywords', 'topics'}

class QdrantCollectionDoesNotExistError(BaseError):
    ...