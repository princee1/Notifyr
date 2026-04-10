from typing import Any, Dict, List, Literal, Optional, Self, Tuple
from aiohttp_retry import Union
from pydantic import BaseModel, Field, HttpUrl, PrivateAttr, field_serializer, field_validator, model_validator
from app.classes.embeddings import EmbeddingWrapper
from app.classes.url import ComparableURL, URLParam
from app.models.crawal4ai_model import MAX_URLS, DeepCrawlingStrategyModel, DigestConfigModel,KnowledgeGraphExtractionConfig, PDFLinkPreviewModel, SchemaExtractionConfig, SeedingURLModel, TextsExtractionConfig, URLGeneratorModel
from app.utils.constant import ArqDataTaskConstant, ParseStrategy
from app.utils.helper import SliceMode
from .file_model import FileResponseUploadModel, UriMetadata
from app.classes.scheduler import TimedeltaSchedulerModel


###################################################################################################
###########################	          Base Ingest Model				 ##############################
###################################################################################################
class VectorConfig(BaseModel):
	collection_name: str
	category: str
	
class KGraphConfig(BaseModel):
	domain:str
	entities:Optional[list[str]] = Field(default_factory=list)
	edges:Optional[list[str]] = Field(default_factory=list)
	description:Optional[str] = None
	instruction:Optional[str] = None

class DataIngestModel(BaseModel):
	vector_config: Optional[VectorConfig] =  None
	graph_config: Optional[KGraphConfig] = None
	lang: Optional[str] = 'en'
	expires: Optional[TimedeltaSchedulerModel|None] = None
	defer_by: Optional[TimedeltaSchedulerModel|None] = None

	@field_validator('expires','defer_by')
	def transform_into_timedelta(cls,tDelta:TimedeltaSchedulerModel|None):
		if tDelta == None:
			return None
		delta = tDelta.build('timedelta')
		if delta.total_seconds() <= 10:
			return None
		return delta

	@field_serializer("defer_by","expires")
	def time_serialize(cls, v:TimedeltaSchedulerModel):
		return v.build('timedelta').total_seconds()

	@model_validator(mode='after')
	def config_validation(self:Self)->Self:
		if self.vector_config == None and self.graph_config == None:
			raise ValueError('You must define at least one ')

		return self

	@property
	def db_config(self)->Tuple[bool,bool]:
		return (self.vector_config != None,self.graph_config != None)
	
	@property
	def expire_date(self):
		if self.expires:
			return self.expires.build('datetime').isoformat()
		return None

	@property
	def defer_date(self):
		if self.defer_by:
			return self.defer_by.build('datetime').isoformat()
		return None

class BaseIngestModelResponse(BaseModel):
	vector:bool
	graph:bool
	expire:str
	defer:str
	task:ArqDataTaskConstant._DATA_TASK_TYPE

###################################################################################################
###########################		    File Ingest Model			     ##############################
###################################################################################################
class FileUploadDataIngestModel(DataIngestModel):
	strategy: ParseStrategy
	use_docling:bool = False

class FileIngestUriMetadata(UriMetadata):
	sha:str

class FileUploadIngestEnqueueResponse(FileResponseUploadModel, BaseIngestModelResponse):
	metadata: List[FileIngestUriMetadata] = Field(default_factory=list)
	task:str = ArqDataTaskConstant.FILE_DATA_TASK,

###################################################################################################
###########################		   Web Crawling	Ingest Model         ##############################
###################################################################################################

class WebCrawlingDataIngestModel(DataIngestModel):
	extraction:Union[SchemaExtractionConfig | TextsExtractionConfig | KnowledgeGraphExtractionConfig]
	urls: List[HttpUrl] | SeedingURLModel | URLGeneratorModel
	pdf: Optional[PDFLinkPreviewModel] = None
	exclude_external_links:bool = True
	deep_crawling: Optional[DeepCrawlingStrategyModel] = None
	name:str = Field(min_length=10,max_length=20)

	_url_size: Optional[int] = PrivateAttr(default=None)
	_description : Optional[str] = PrivateAttr(default=None)

	@field_validator("name", mode="after")
	def parse_uri(cls,v:str)->str:
		v = v.strip().lower().replace(' ','_')
		if not v.endswith('.crawl'):
			return f"{v}.crawl"
		return v

	@field_validator("urls", mode="before")
	def coerce_urls(cls, v):
		if isinstance(v,str):
			return [v]
		return v

	@field_validator("urls", mode="after")
	def parse_urls(cls, v):
		if isinstance(v,list):
			if len(v) > MAX_URLS *2:
				raise ValueError(f"You cannot provide more than {MAX_URLS *2} urls, you provided {len(v)}")
		return v
		
	@model_validator(mode='after')
	def invalidate_deep_crawling(self:Self)->Self:
		if isinstance(self.urls, URLGeneratorModel) and self.deep_crawling != None:
			raise ValueError('If the urls are generated you cannot use deep crawling as it will use too much ressource')

		return self

	@model_validator(mode='after')
	def validate_db_config(self:Self)->Self:
		if isinstance(self.extraction, KnowledgeGraphExtractionConfig) and self.graph_config == None:
			raise ValueError('If you want to extract a knowledge graph you need to provide a graph_config with at least a domain name and one of those two lists: entities or edges')

		if isinstance(self.extraction,KnowledgeGraphExtractionConfig):
			if not self.graph_config.instruction:
				raise ValueError('')

			if self.graph_config != None:
				if not self.graph_config.entities and not self.graph_config.edges:
					raise ValueError('If you want to extract a knowledge graph you need to provide a graph_config with at least a domain name and one of those two lists: entities or edges')
			else:
				raise ValueError('If you want to extract a knowledge graph you need to provide a graph_config with at least a domain name and one of those two lists: entities or edges')

		return self

	@property
	def pdf_size(self):
		if self.pdf:
			return self.pdf.max_links
		return 0

	def compute_size(self,):
		if isinstance(self.urls,list):
				url_size = len(self.urls)
				description = "Defined urls"

		elif isinstance(self.urls,SeedingURLModel):
			url_size = self.urls.top
			description = "Seeded urls"
		elif isinstance(self.urls,URLGeneratorModel):
			url_size = 1
			description = "URL generated"
			for param in {**self.urls.path_params, **self.urls.query_params}.values():
				if isinstance(param, list):
					url_size *= len(param)
				else:
					start,stop,step = param
					url_size *= ((stop - start) // step) + 1
		
		self._url_size = url_size
		self._description = description

	@property
	def subject(self)->str:
		return self.extraction.subject

class CrawlingComparableURL(ComparableURL):

	def __init__(self,ingestTask:WebCrawlingDataIngestModel):
		self.ingestTask=ingestTask
					
	def __eq__(self, value:dict|list):
		if isinstance(self.ingestTask.urls,list) and isinstance(value,list):
			return self.compare_url(self.ingestTask.urls,value)
					
		elif isinstance(self.ingestTask.urls,SeedingURLModel) and isinstance(value,dict):
			if 'domain' not in value:
				return False
			
			return self.compare_url(self.ingestTask.urls.domain,value)
		
		elif isinstance(self.ingestTask.urls,URLGeneratorModel):
			if 'base_url' not in value:
				return False
			
			if self.ingestTask.urls.base_url != value['base_url']:
				return False
			
			params = self.compare_param(self.ingestTask.urls.path_params,value['path_params'])
			query =  self.compare_param(self.ingestTask.urls.query_params,value['query_params'])

			return params and query

class ComparableEmbeddings:
	def __init__(self,embedding:EmbeddingWrapper|None, mode:Literal['filter','compare'],filter_mode:SliceMode='include'):
		self.mode = mode
		self.filter_mode = filter_mode
		self.embedding = embedding
		self.filtered:set[str] = set()

	def __eq__(self,other:dict):
		target_embedding = EmbeddingWrapper(other)
		is_similar = (self == target_embedding)
		
		if self.mode == 'filter':
			if is_similar == (self.filter_mode == 'include'):
				self.filtered.add(target_embedding.vector_id)
			if (not is_similar) == (self.filter_mode == 'exclude'):
				self.filtered.add(target_embedding.vector_id)
			return True
		else:
			return is_similar

class WebCrawlingUriMetadata(UriMetadata):
	description: Optional[str] = None
	pdf_size: Optional[int] = None
	url_size: Optional[int] = None

class WebCrawlingIngestDataResponse(BaseIngestModelResponse):
	metadata: Optional[WebCrawlingUriMetadata] = None
	task:ArqDataTaskConstant._DATA_TASK_TYPE = ArqDataTaskConstant.CRAWL_DATA_TASK

###################################################################################################
###########################		      Research Ingest Model	         ##############################
###################################################################################################

class ResearchDataIngestModel(DataIngestModel):
	engine:Literal['google','bing','duckduckgo','google-scholar'] = 'google'
	max_pages: int = Field(default=10, gt=0, le=10)
	query:str
	config:DigestConfigModel

class ResearchIngestUriMetadata(UriMetadata):
	...

class ResearchIngestDataResponse(BaseIngestModelResponse):
	...


###################################################################################################
###########################				API Data Ingest Model	     ##############################
###################################################################################################


class APIIngestDataResponse(BaseIngestModelResponse):
	...

###################################################################################################
###########################			Delete Ingest Model				 ##############################
###################################################################################################

class DeleteIngestUriMetadata(UriMetadata):
	task:ArqDataTaskConstant._DATA_TASK_TYPE

class DeleteIngestBaseModel(BaseModel):
	metadata:List[DeleteIngestUriMetadata] = Field(default_factory=list)

class DeleteIngestDataModel(DeleteIngestBaseModel):
	errors:Dict[str,DeleteIngestUriMetadata]
	job_dequeued:List[str] = Field(default_factory=list)
	jod_deleted:List[str] = Field(default_factory=list)
	gateway_body:Optional[Dict] = None

class AbortedJobResponse(DeleteIngestBaseModel):
	deleted:bool = False
	aborted:bool = False
	dequeued:bool = False
	status:str

###################################################################################################
###########################										     ##############################
###################################################################################################

