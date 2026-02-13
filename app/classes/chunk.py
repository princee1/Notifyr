from typing import TypedDict, Optional, Any

class ChunkPayload(TypedDict):
    text: str
    document_name: str
    document_id: str
    node_id: str
    source: Optional[str]
    extension: str
    strategy: str
    parser: str
    page: Optional[Any]
    bbox: Optional[Any]
    chunk_id: str
    chunk_index: int
    title: str
    section: str
    language: str
    content_type: str
    document_type: str
    category: str
    token_count: int
    full_token_count: int
    word_count: int
    most_common: list[tuple[str, int]]
    sentence_count: int
    keywords: list[str]
    topics: list[str]
    density: str
    relationship: list[str]

class Chunk:

    def __init__(self,chunk_id:str,vector:list[float],payload:ChunkPayload,category:str,lang:str):
        self.chunk_id = chunk_id
        self.vector = vector
        self.payload = payload
        self.category = category
        self.lang = lang
