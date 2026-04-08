import math
from typing import Any, Dict, List, Literal, Optional, Self, Tuple
from pydantic import BaseModel, Field, model_validator, field_validator
from pydantic import HttpUrl

from app.classes.url import JSONLDFilterGroup, URLConfigModel

DeepCrawlingAlgorithm = Literal['bfs','dfs','best-first']
ExtractionMode = Literal['markdown', 'structured']
StructuredExtractionFormat = Literal['text_list', 'dictionary', 'list_of_dictionaries', 'knowledge_graph']
StructuredExtractionStrategy = Literal['llm', 'json'] #'regex'


MAX_URLS = 10

###################################################################################################
###########################		  DeepCrawling Models			     	 ##########################
###################################################################################################

class ScorerModel(BaseModel):
	mode: Literal['keyword', 'domain_authority', 'path_depth', 'content_type', 'freshness']
	weight: float = Field(gt=0, default=0.25)
	keyword: Optional[List[str]] = None
	domain_weights: Optional[Dict[str, float]] = None
	default_weight: Optional[float] = None
	current_year: Optional[int] = None
	type_weights: Optional[Dict[str, float]] = None

	@model_validator(mode='after')
	def validate_mode_fields(self: Self) -> Self:
		if self.mode == 'keyword':
			if not self.keyword:
				raise ValueError("'keyword' mode requires 'keyword' list to be non-empty")
			if self.domain_weights or self.default_weight or self.current_year or self.type_weights:
				raise ValueError("'keyword' mode only accepts 'weight' and 'keyword' fields")
		
		elif self.mode == 'domain_authority':
			if not self.domain_weights:
				raise ValueError("'domain_authority' mode requires 'domain_weights' dictionary")
			if self.keyword or self.current_year or self.type_weights:
				raise ValueError("'domain_authority' mode only accepts 'weight', 'domain_weights', and optional 'default_weight'")
		
		elif self.mode == 'path_depth':
			if self.keyword or self.domain_weights or self.current_year or self.type_weights:
				raise ValueError("'path_depth' mode only accepts 'weight' field")
		
		elif self.mode == 'content_type':
			if not self.type_weights:
				raise ValueError("'content_type' mode requires 'type_weights' dictionary")
			if self.keyword or self.domain_weights or self.current_year:
				raise ValueError("'content_type' mode only accepts 'weight' and 'type_weights' fields")
		
		elif self.mode == 'freshness':
			if self.keyword or self.domain_weights or self.type_weights:
				raise ValueError("'freshness' mode only accepts 'weight' and optional 'current_year'")
		
		return self

class FilterModel(BaseModel):
	mode: Literal['url_pattern', 'domain', 'content_type', 'content_relevance', 'seo']
	threshold: float = Field(ge=0, le=1, default=0.5)
	patterns: Optional[List[str]] = None
	include_domains: Optional[List[str]] = None
	blocked_domains: Optional[List[str]] = None
	allowed_types: Optional[List[str]] = None
	query: Optional[str] = None
	similarity_threshold: Optional[float] = None
	keywords: Optional[List[str]] = None

	@model_validator(mode='after')
	def validate_mode_fields(self: Self) -> Self:
		if self.mode == 'url_pattern':
			if not self.patterns:
				raise ValueError("'url_pattern' mode requires 'patterns' list to be non-empty")
			if self.include_domains or self.blocked_domains or self.allowed_types or self.query or self.similarity_threshold or self.keywords:
				raise ValueError("'url_pattern' mode only accepts 'threshold' and 'patterns' fields")
		
		elif self.mode == 'domain':
			if not self.include_domains and not self.blocked_domains:
				raise ValueError("'domain' mode requires either 'include_domains' or 'blocked_domains'")
			if self.patterns or self.allowed_types or self.query or self.similarity_threshold or self.keywords:
				raise ValueError("'domain' mode only accepts 'include_domains' and 'blocked_domains'")
		
		elif self.mode == 'content_type':
			if not self.allowed_types:
				raise ValueError("'content_type' mode requires 'allowed_types' list")
			if self.patterns or self.include_domains or self.blocked_domains or self.query or self.similarity_threshold or self.keywords:
				raise ValueError("'content_type' mode only accepts 'allowed_types'")
		
		elif self.mode == 'content_relevance':
			if not self.query:
				raise ValueError("'content_relevance' mode requires 'query' text")
			if self.patterns or self.include_domains or self.blocked_domains or self.allowed_types or self.keywords:
				raise ValueError("'content_relevance' mode only accepts 'threshold', 'query', and optional 'similarity_threshold'")
			if self.similarity_threshold is not None and not (0 <= self.similarity_threshold <= 1):
				raise ValueError("'similarity_threshold' must be between 0 and 1")
		
		elif self.mode == 'seo':
			if self.patterns or self.include_domains or self.blocked_domains or self.allowed_types or self.query or self.similarity_threshold:
				raise ValueError("'seo' mode only accepts 'threshold' and optional 'keywords'")
		
		return self

class DeepCrawlingStrategyModel(BaseModel):
	algorithm: DeepCrawlingAlgorithm = 'best-first'
	max_pages: float = Field(ge=1, le=100, default=50)
	max_depth: float = Field(ge=0, le=10, default=2)
	include_external: bool = False
	score_threshold: Optional[float] = None
	url_scorers: Optional[List[ScorerModel]] = None
	url_filters: Optional[List[FilterModel]] = None

	
	@field_validator("max_pages", mode="after")
	def check_pages(cls, v):
		if v == 0:
			raise ValueError('Max Pages cannot be 0, it should be at least 1, or None ("inf", for infinity),')
		return v

	@field_validator("score_threshold", mode="after")
	def check_score(cls, v):
		if v is None:
			return -math.inf
		if not (0 <= v <= 1):
			raise ValueError("score_threshold must be between 0 and 1")
		return v


###################################################################################################
###########################		  URL Models			     			 ##########################
###################################################################################################

class SeedingURLModel(BaseModel):
	domain:List[HttpUrl] = Field(description="List of domains to seed the crawl (e.g., ['example.com', 'anotherdomain.com'])",max_length=MAX_URLS,min_length=1)
	source:Literal['cc','sitemap','sitemap+cc'] = 'sitemap'
	max_urls:int =  Field(default=25,ge=1, le=50, description="Max url for each domain")
	score_threshold: Optional[float] = Field(default=0.4,gt=0,lt=1)
	queries:Optional[List[str]] = []
	pattern: Optional[str] =  None
	#speed: Literal['normal','fast','ultra-fast'] = 'fast'
	top: Optional[int] = Field(default=None, ge=1, description="Max urls to crawl, if None it will crawl all the urls found respecting the max_urls for each domain")
	jsonld:Optional[JSONLDFilterGroup] = None


	@field_validator('queries',mode='after')
	def validate_queries(cls,q:list):
		if len(q) == 0:
			q.append('')
		
		return list(set(q))
	
	@field_validator("domain", mode="before")
	def parse_domain(cls, v):
		if isinstance(v,str):
			return [v]
		return v

	@field_validator("pattern",mode="after")
	def validate_pattern(cls,p:str):
		if p == None:
			return "*"

		if not p.startswith('*') and not p.endswith('*'):
			return f"*{p}*"
		
		return p

	@field_validator("domain", mode="after")
	def validate_domain(cls,d:list):
		len_domain = len(d)

		if len_domain == 0:
			raise ValueError('At least one domain must be define')
		
		if len_domain > 100:
			raise ValueError(f'Maximum domain reached: max:100 got {len_domain}')
		
		return list(set(d))

	@model_validator(mode='after')
	def validate_top(self:Self)->Self:
		
		max_top = self.max_urls * len(self.domain)

		if self.top is not None and self.top < max_top:
			raise ValueError(f"If 'top' is defined it should be inferior to max_urls * number of domains, got top: {self.top} > {max_top}")	
		else:
			self.top = max_top

		return self

class URLGeneratorModel(URLConfigModel):
	jsonld:Optional[JSONLDFilterGroup] = None

	@field_validator("path_params","query_params",mode="after")
	def validate_path_params(cls, v):
		if len(v) > 5:
			raise ValueError("You cannot have more than 5 path or query parameters for url generation")
		if len(v) == 0:
			raise ValueError("You must have at least one path or query parameter for url generation")
		return v

###################################################################################################
###########################		  Research Models			     		 ##########################
###################################################################################################

class DigestConfigModel(BaseModel):
	strategy: Literal["embedding", "statistical"] = Field(default="embedding", description="Strategy type")
	confidence_threshold: float = Field(default=0.7, ge=0, le=1, description="Confidence threshold between 0 and 1")
	max_depth: int = Field(default=3, ge=1, description="Maximum depth, must be at least 1")
	max_pages: int = Field(default=20, ge=1, description="Maximum number of pages, must be at least 1")
	top_k_links: int = Field(default=3, ge=1, description="Top K links to consider, must be at least 1")
	min_gain_threshold: float = Field(default=0.1, ge=0, le=1, description="Minimum gain threshold between 0 and 1")

	relevance_weight: float = Field(default=0.5, ge=0, le=1, description="Relevance weight between 0 and 1")
	novelty_weight: float = Field(default=0.3, ge=0, le=1, description="Novelty weight between 0 and 1")
	authority_weight: float = Field(default=0.2, ge=0, le=1, description="Authority weight between 0 and 1")

	n_query_variations: int = Field(default=10, ge=1, description="Number of query variations, must be at least 1")
	coverage_threshold: float = Field(default=0.85, ge=0, le=1, description="Coverage threshold between 0 and 1")
	embedding_overlap_threshold: float = Field(default=0.85, ge=0, le=1, description="Embedding overlap threshold between 0 and 1")
	embedding_k_exp: float = Field(default=3.0, ge=0, le=12,description="Exponential decay factor for embedding overlap (higher = stricter)")

	# Stopping criteria
	embedding_min_relative_improvement: float = Field(default=0.1, ge=0, le=1, description="Minimum relative improvement in embedding overlap to continue")
	embedding_validation_min_score: float = Field(default=0.3, ge=0, le=1, description="Minimum validation score for embeddings")
	embedding_min_confidence_threshold: float = Field(default=0.1, ge=0, le=1, description="Minimum confidence threshold below which results are considered irrelevant")

###################################################################################################
###########################		  Extraction Mode Models			     ##########################
###################################################################################################

class BaseExtractionConfig(BaseModel):
    """Common fields shared across all extraction configurations."""
    instruction: Optional[str] = Field(default=None, description="LLM instruction for extraction")

class TextsExtractionConfig(BaseExtractionConfig):
    """Configuration for extracting list of text items (id, name, text)."""
    focus: str

class SchemaExtractionConfig(BaseExtractionConfig):
	"""Configuration for extracting list of dictionary objects."""
	schema_name: Optional[str] = Field(default=None, description="Schema name for json_css/regex strategy")
	schema_url: Optional[str] = Field(default=None, description="Example URL to generate schema from")
	custom_schema: Optional[str] = Field(default=None, description="Name of the predefined schema to use (e.g., 'product', 'article')")
	strategy: StructuredExtractionStrategy = 'llm'

class KnowledgeGraphExtractionConfig(BaseExtractionConfig):
    """Configuration for extracting knowledge graph (entities and relationships)."""
    strategy: Optional[Literal['kg-llm']] = 'kg-llm' 


###################################################################################################
###########################		   PDF Link Preview  Model 			     ##########################
###################################################################################################

class PDFLinkPreviewModel(BaseModel):
	max_links: int = Field(default=5, ge=1, le=20, description="Maximum number of PDF links to preview")
	score_threshold: Optional[float] = Field(default=0.6, ge=0, le=1, description="Score threshold for including PDF links in the preview")
	query: Optional[str] = Field(default=None, description="Optional query to evaluate relevance of PDF links",max_length=250,min_length=2)

