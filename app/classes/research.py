from dataclasses import dataclass

from pydantic import BaseModel, Field
from typing import List, Literal, Optional, TypedDict
from datetime import datetime
from urllib.parse import quote

from requests.compat import urlparse
from urllib.parse import parse_qs
from app.classes.url import URLConfigModel, URLParam
from app.definition._error import BaseError

class SearchEngineNotSupportedError(BaseError):
    def __init__(self,engine:str ):
        super().__init__()
        self.engine = engine


EXAMPLE_SCHEMA_NAME = 'search_result'
EXAMPLE_SEARCH_QUERY= 'Machine Learning'

class QueryExpansionModel(BaseModel):
    concepts:List[str]


class SearchLinkResultModel(BaseModel):
    """Represents a single search result from a search engine."""
    
    title: str = Field(..., description="Title of the search result")
    url: str = Field(..., description="Direct URL of the result")
    description: str = Field(..., description="Snippet/preview text from the result")
    position: int = Field(..., ge=1, description="Rank position in search results (1-indexed)")
    
    # Optional fields specific to certain engines
    date_published: Optional[datetime] = Field(None, description="Publication date (if available)")
    cite_count: Optional[int] = Field(None, ge=0, description="Citation count (Google Scholar)")
    author: Optional[str] = Field(None, description="Author name (mainly for Scholar)")
    domain: Optional[str] = Field(None, description="Domain/source domain of the result")
    rating: Optional[float] = Field(None, ge=0, le=5, description="Relevance or quality rating")
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Introduction to Machine Learning",
                "url": "https://example.com/ml-intro",
                "description": "Learn the fundamentals of machine learning with Python and scikit-learn.",
                "position": 1,
                "date_published": "2024-01-15T10:30:00",
                "cite_count": None,
                "author": None,
                "domain": "example.com",
                "rating": 4.5
            }
        }

SearchEngine = Literal['google','bing','google-scholar','yahoo']

def search_query_creator(queries:list[str], engine:SearchEngine, max_pages:int) -> URLConfigModel:
    """
    Create a URLConfigModel for a search engine that generates URLs for multiple pages.
    
    Args:
        query: Search query string
        engine: Search engine type
        max_pages: Maximum number of pages to generate
    
    Returns:
        URLConfigModel configured with pagination parameters for the specified engine
    """
    queries = [quote(q) for q in queries]
    
    match engine:
        case 'google':
            end_offset = max(0, (max_pages - 1) * 10)
            values=(0, 10, end_offset)
            base_url = "https://www.google.com/search?q={{query}}&start={{pages}}"
        case 'bing':
            end_offset = max(1, (max_pages - 1) * 10 + 1)
            values=(1, 10, end_offset)
            base_url = "https://www.bing.com/search?q={{query}}&first={{pages}}"
        case 'duckduckgo':
            base_url = "https://duckduckgo.com/?q={{query}}"
            values=(1, 1, max_pages)
        case 'google-scholar':
            end_offset = max(0, (max_pages - 1) * 10)
            values=(0, 10, end_offset)
            base_url = "https://scholar.google.com/scholar?q={{query}}&start={{pages}}"
        case 'yahoo':
            end_offset = max(1, (max_pages - 1) * 10 + 1)
            values=(1, 10, end_offset)
            base_url = "https://search.yahoo.com/search?p={{query}}&b={{pages}}"
        case _:
            raise SearchEngineNotSupportedError(engine)
        
    return URLConfigModel(
            base_url=base_url,
            query_params={
                'query':URLParam(
                    type='list',
                    values=queries
                ),
                'pages': URLParam(
                    type='range',
                    values=values
                )
            }
        )

def search_example_url(engine:SearchEngine):
    match engine:
        case 'bing':
            return f"https://www.bing.com/search?q={EXAMPLE_SEARCH_QUERY}"
        case 'google':
            return f"https://www.google.com/search?q={EXAMPLE_SEARCH_QUERY}"
        case 'yahoo':
            return f"https://search.yahoo.com/search?p={EXAMPLE_SEARCH_QUERY}"
        case 'google-scholar':
            return f"https://scholar.google.com/scholar?q={EXAMPLE_SEARCH_QUERY}"
        case _:
            raise SearchEngineNotSupportedError(engine)



def extract_query(url: str, engine: SearchEngine):
    url_obj = urlparse(url)
    params = parse_qs(url_obj.query)
    match engine:
        case 'yahoo':
            return params.get('p', [None])[0]
        case _:
            return params.get('q', [None])[0]
        

class SearchLinkState(TypedDict):
    query:str
    content:dict

@dataclass
class ResearchResultMetadata:
    markdown:str
    source:str
    description:str
    title:str
    error_message:str
    success:bool

class ResearchDocument(TypedDict):
    url:str
    score:float
    content:str
    index:int
