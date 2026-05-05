from typing import TypedDict, Optional, Any, Literal

CONTEXT_KEYS = {'text','document_name','document_id','source','title','section','relationship'}

Density = Literal['low','medium','high']
DocumentType = Literal['textfile','webpage']
Extension = Literal["pdf", "docx", "md", "html", "pptx", "txt",'xml']

class Chunk(TypedDict):
    chunk_id:str
    text:str
    document_name:str
    document_id:str
    source:str
    title:str
    section:str
    relationship:list[str]

class ChunkContext(Chunk):
    vector:list[float]
    similarity:float

class ChunkPayload(Chunk):
    #info
    extension: Extension
    language: str
    document_type: DocumentType

    strategy: str
    parser: str
    page: Optional[Any]
    bbox: Optional[Any]
    index: int
    content_type: str

    #stats
    token_count: int
    full_token_count: int
    word_count: int
    most_common: list[tuple[str, int]]
    sentence_count: int

    #words
    keywords: list[str]
    topics: list[str]
    density: Density

class ChunkMultimediaPayload(TypedDict):
    ...

class ChunkDataPointsPayload(TypedDict):
    ...


class ChunkWrapper:

    def __init__(self,chunk_id:str,vector:list[float],payload:ChunkPayload,category:str,lang:str):
        self.chunk_id = chunk_id
        self.vector = vector
        self.payload = payload
        self.category = category
        self.lang = lang