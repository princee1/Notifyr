from typing import Any, Dict, List, Literal, Optional, Self, Tuple
from aiohttp_retry import Union
from pydantic import BaseModel, Field, HttpUrl, field_serializer, field_validator, model_validator
from app.classes.url import URLParam
from app.models.crawal4ai_model import MAX_URLS, DeepCrawlingStrategyModel, DigestConfigModel,KnowledgeGraphExtractionConfig, PDFLinkPreviewModel, SchemaExtractionConfig, SeedingURLModel, TextsExtractionConfig, URLGeneratorModel
from app.utils.constant import ParseStrategy
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
	entities:Optional[list[str]] = []
	edges:Optional[list[str]] = []
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


###################################################################################################
###########################		    File Ingest Model			     ##############################
###################################################################################################
class FileUploadDataIngestModel(DataIngestModel):
	strategy: ParseStrategy
	use_docling:bool = False

class IngestDataUriMetadata(UriMetadata):
	sha:str

class FileUploadIngestEnqueueResponse(FileResponseUploadModel):
    metadata: List[IngestDataUriMetadata] = []
	
class AbortedJobResponse(FileResponseUploadModel):
	aborted:bool
	status:str
	
###################################################################################################
###########################		           Web Crawling			     ##############################
###################################################################################################

class WebCrawlingDataIngestModel(DataIngestModel):
	extraction:Union[SchemaExtractionConfig | TextsExtractionConfig | KnowledgeGraphExtractionConfig]
	urls: List[HttpUrl] | SeedingURLModel | URLGeneratorModel
	pdf: Optional[PDFLinkPreviewModel] = None
	exclude_external_links:bool = True
	deep_crawling: Optional[DeepCrawlingStrategyModel] = None
	name:str = Field(min_length=10,max_length=20)

	@field_validator("uri", mode="after")
	def parse_uri(cls,v:str)->str:
		v = v.strip().lower().replace(' ','_')
		if not v.endswith('.crawl'):
			return f"{v}.crawl"
		return v

	@field_validator("urls", mode="before")
	def parse_urls(cls, v):
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
			if self.graph_config != None:
				if not self.graph_config.entities and not self.graph_config.edges:
					raise ValueError('If you want to extract a knowledge graph you need to provide a graph_config with at least a domain name and one of those two lists: entities or edges')
			else:
				raise ValueError('If you want to extract a knowledge graph you need to provide a graph_config with at least a domain name and one of those two lists: entities or edges')

		return self

class ComparableURL:

	def __init__(self,ingestTask:WebCrawlingDataIngestModel):
		self.ingestTask=ingestTask

	def compare_url(self,ptr:list,value:list):
		urls = list(set(ptr).difference(value))
		if not urls:
			return True

		ptr.clear()
		ptr.extend(urls)
		return False
	
	def compare_param(self, ptr: Dict[str, URLParam], value: Dict[str, dict]):
		keys_to_remove = []
		
		for key in ptr.keys():
			if key not in value:
				continue
			
			ptr_param = ptr[key]
			ptr_values = ptr_param.values
			value_values = value[key]
			
			if isinstance(ptr_values, list) and value_values['type'] == 'list':
				diff = list(set(ptr_values) - set(value_values))
				if not diff:
					keys_to_remove.append(key)
				else:
					ptr_param.values = diff
			
			elif isinstance(ptr_values, tuple) and value_values['type']=='range':
				if ptr_values == tuple(value_values['values']):
					keys_to_remove.append(key)
					continue
				try:
					v = URLParam(type='range',values=tuple(value_values['values']))
					temp = URLParam(type='range',values=ptr_values,exclude=v)
					ptr[key] = temp
				except:
					keys_to_remove.append(key)
				
			else:
				keys_to_remove.append(key)
		
		for key in keys_to_remove:
			del ptr[key]
		
		return len(ptr) == 0
					
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

class ComparableInstruction:
	def __init__(self,ingestTask:WebCrawlingDataIngestModel,threshold:int=0.8):
		self.ingestTask=ingestTask
		self.threshold=threshold
	
	async def search(self)->bool:
		...

class IngestDataWebCrawlingResponse(UriMetadata):
	...


###################################################################################################
###########################										     ##############################
###################################################################################################

class ResearchDataIngestModel(DataIngestModel):
	engine:Literal['google','bing','duckduckgo','google-scholar'] = 'google'
	max_pages: int = Field(default=10, gt=0, le=10)
	query:str
	config:DigestConfigModel


###################################################################################################
###########################										     ##############################
###################################################################################################


class EnqueueResponse(FileResponseUploadModel):
	...
