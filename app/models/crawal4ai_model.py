import math
from typing import Dict, List, Literal, Optional, Self, Tuple
from pydantic import BaseModel, Field, model_validator,field_validator, model_validator

from app.classes.crawl import JSONLDFilterGroup, URLConfigModel

DeepCrawlingAlgorithm = Literal['bfs','dfs','best-first']

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

class DeepCrawlingStrategyModel(BaseModel):
	algorithm: DeepCrawlingAlgorithm = 'best-first'
	max_pages: float = Field(ge=1, default=50, allow_inf_nan=True)
	max_depth: float = Field(ge=0, default=2, allow_inf_nan=True)
	include_external: bool = False
	score_threshold: Optional[float] = None
	url_scorers: Optional[List[ScorerModel]] = None
	url_filters: Optional[List[FilterModel]] = None

	@field_validator("max_pages", "max_depth", mode="before")
	def parse_unlimited(cls, v):
		if v in ("inf", "infinity", -1, None):
			return math.inf
		return v
	
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

class ExtractionStrategyModel(BaseModel):
	mode:Literal['']
	recursive:str
	schema_url:str

class SeedingURLModel(BaseModel):
	domain:List[str]
	source:Literal['cc','sitemap','sitemap+cc'] = 'sitemap'
	max_urls:int =  Field(default=50,ge=-1,description="Max url for each domain")
	score_threshold: Optional[float] = Field(default=0.4,gt=0,lt=1)
	queries:Optional[List[str]] = []
	pattern: Optional[str] =  None
	#speed: Literal['normal','fast','ultra-fast'] = 'fast'
	top: Optional[int] = None 
	jsonld:Optional[JSONLDFilterGroup] = None


	@field_validator('queries',mode='after')
	def validate_queries(cls,q:list):
		if len(q) == 0:
			q.append('')
		
		return list(set(q))

	@field_validator("max_url", mode="before")
	def parse_unlimited(cls, v):
		if v in ("inf", "infinity", -1, None):
			return -1
		return v
	
	@field_validator("max_url", mode="after")
	def validate_max_url(cls,v):
		if v ==0:
			raise ValueError('max_url must be inf or >= 1')
		return v
	
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
			raise ValueError(f'Maximum domain reached: max:200 got {len_domain}')
		
		return list(set(d))

	@model_validator(mode='after')
	def validate_top(self:Self)->Self:
		
		if self.top != None and self.top <1:
			raise ValueError('Top urls cannot be less than 1')

		if self.max_urls != -1:
			
			all_url = len(self.queries) * self.max_urls

			if  self.top != None and self.top > all_url:
				self.top = all_url

		return self

class URLGeneratorModel(URLConfigModel):
	jsonld:Optional[JSONLDFilterGroup] = None
