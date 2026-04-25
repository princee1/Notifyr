"""
Complete Web Crawler Ingestion with support for multiple extraction modes.
Handles URL generation, content extraction, chunk splitting, and token tracking.
"""
import asyncio
from enum import Enum
import json
from pathlib import Path
import sys
from typing import AsyncGenerator, Callable, Dict, List, Literal, Optional, Type

import aiohttp
from bs4 import BeautifulSoup
from crawl4ai import AsyncUrlSeeder, AsyncWebCrawler, BrowserConfig, CrawlResult, CrawlerRunConfig, CacheMode, LinkPreviewConfig, PruningContentFilter, SeedingConfig
from crawl4ai import LLMConfig, LLMExtractionStrategy, JsonCssExtractionStrategy, RegexExtractionStrategy,ExtractionStrategy
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy, DFSDeepCrawlStrategy, BestFirstCrawlingStrategy, DeepCrawlStrategy
from crawl4ai.processors.pdf import PDFCrawlerStrategy, PDFContentScrapingStrategy
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.deep_crawling.scorers import (
	KeywordRelevanceScorer, DomainAuthorityScorer, PathDepthScorer, 
	ContentTypeScorer, CompositeScorer, FreshnessScorer, urlparse
)
from crawl4ai.deep_crawling.filters import (
	URLPatternFilter, DomainFilter, ContentTypeFilter, 
	ContentRelevanceFilter, SEOFilter, FilterChain
)
from crawl4ai.models import TokenUsage

from pydantic import BaseModel
from app.classes.chunk import ChunkPayload, Chunk, TextDetector
from app.classes.cost_definition import MarkdownCostDefinition
from app.classes.crawl import *
from app.classes.url import fetch_jsonld, generate_urls
import re
from app.models.crawal4ai_model import (
	DeepCrawlingAlgorithm, DeepCrawlingStrategyModel,
	TextsExtractionConfig, SchemaExtractionConfig, SchemaExtractionConfig,
	KnowledgeGraphExtractionConfig,
	SeedingURLModel, URLGeneratorModel
)
from app.models.ingest_model import WebCrawlingDataIngestModel
from app.prompt import crawl_prompt, graphiti_prompt
from app.utils.constant import Crawl4AIConstant
from app.utils.tools import RunAsync


###################################################################################################
###########################		  DEEP_CRAWL_MAP					     ##############################
###################################################################################################

DEEP_CRAWL_MAP: Dict[DeepCrawlingAlgorithm, Type[DeepCrawlStrategy]] = {
	'bfs': BFSDeepCrawlStrategy,
	'dfs': DFSDeepCrawlStrategy,
	'best-first': BestFirstCrawlingStrategy,
}

EXTRACTION_STRATEGY_MAP :Dict[Literal['json','regex'],type[ExtractionStrategy]] = {
	'json': JsonCssExtractionStrategy,
	'regex':RegexExtractionStrategy
}

###################################################################################################
###########################		  WebCrawlerIngestion Class			     ##############################
###################################################################################################

MS = 1000

# A list of the most frequent ad, tracking, and spam-heavy domains
AD_AND_SPAM_DOMAINS = [
    "doubleclick.net",
    "googleadservices.com",
    "googlesyndication.com",
    "adnxs.com",
    "advertising.com",
    "adtech.com",
    "taboola.com",
    "outbrain.com",
    "openx.net",
    "pubmatic.com",
    "rubiconproject.com",
    "casalemedia.com",
    "yieldmo.com",
    "media.net",
    
    "scorecardresearch.com",
    "quantserve.com",
    "fullstory.com",
    "hotjar.com",
    "crazyegg.com",
    "mixpanel.com",
    "segment.io",
    "intercom.io",
    
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "clickbank.net",
    "revenuehits.com",
    "bidvertiser.com",
    "popads.net",
    "propellerads.com"
]



class CrawlIngestionStepIndex(int, Enum):
	CRAWL = 1
	TOTAL_COST = 2
	CLEANUP = 3

class WebCrawlerIngestion:
	"""
	Comprehensive web crawler ingestion system with support for:
	- Multiple extraction modes (markdown, structured)
	- Deep crawling with scoring and filtering
	- Schema generation and caching
	- Token usage tracking
	- Chunk splitting and semantic preservation
	"""
	
	def __init__(
		self,
		ingestTask: WebCrawlingDataIngestModel,
		crawl_llm_config: CrawlLLMConfig,
		markdownCostDefinition:MarkdownCostDefinition,
		crawl_state: Optional[WebCrawlState] = None,
		extra_headers: Optional[Dict] = None,
		dc_state_callback: Optional[Callable[[WebCrawlState], None]] = None,
		base_dir: Optional[str] = None,
		schema:Optional[Type[BaseModel]] = None,
	):
		self.session_id: str | Callable[[], str] = ...
		self.extra_headers = extra_headers

		self.ingestTask = ingestTask
		self.crawlLlmConfig = crawl_llm_config
		self.dc_state_callback = dc_state_callback
		self.crawlState = crawl_state
		self.schema = schema

		self.max_markdown_def = markdownCostDefinition
		self.schema_dir = Path(base_dir) / Crawl4AIConstant.CRAWL_CACHE_DIR / 'schemas'
		self.cache_dir = Path(base_dir) / Crawl4AIConstant.CRAWL_CACHE_DIR / 'cache'
		
		self.errors: list[CrawlError]  = []
		self.crawler: Optional[AsyncWebCrawler] = None
		self.llm_config: Optional[LLMConfig] = None
		self.deep_crawl_strategy: Optional[DeepCrawlStrategy] = None
		
		self.urls: List[str] = []
		self.documents:List[MarkdownDocumentSize] = []
	
	def init_crawler(self):
		self.crawler = AsyncWebCrawler(
			config=BrowserConfig(
				headless=True,
				use_managed_browser=False,
				accept_downloads=False,
				user_agent_mode='random',
			),
			session_id=self.session_id() if callable(self.session_id) else self.session_id,
			#base_directory=self.base_dir
		)

	async def initialize_config(self):
		"""Build crawler and LLM configuration."""
		
		provider_str = self.crawlLlmConfig.formatted_provider()

		self.llm_config = LLMConfig(
			provider=provider_str,
			**self.crawlLlmConfig.model.model_dump(exclude={'model'}),
			api_token=self.crawlLlmConfig.api_token
		)
		self.urls = await self.generate_urls()

		if self.ingestTask.deep_crawling:
			self._build_deepCrawl_strategy()
		
		self.schema_tokenUsage = TokenUsage()
		markdown_generator,strategy  = await self.build_strategy()
	
		self.strategy: LLMExtractionStrategy | JsonCssExtractionStrategy | RegexExtractionStrategy | None = strategy

		pdfLinkPreview = LinkPreviewConfig(
			include_external=True,
			include_patterns=['*.pdf'],
			timeout=3,
			**self.ingestTask.pdf.model_dump(exclude_none=True)
		) if self.ingestTask.pdf else None
		
		self.crawl_config = CrawlerRunConfig(
			link_preview_config=pdfLinkPreview,
			preserve_https_for_internal_links=True,
			deep_crawl_strategy=self.deep_crawl_strategy,
			markdown_generator=strategy,
			extraction_strategy=markdown_generator,
			cache_mode=CacheMode.BYPASS,
			exclude_external_images=True,
			wait_for_images=False,
			scan_full_page=True,
			max_scroll_steps=1000,
			score_links=True,
			remove_forms=True,
			exclude_all_images=True,
			excluded_tags=['script', 'style','header'], # Could be used to exclude scripts, styles, etc. if needed
			simulate_user=True,
			exclude_social_media_links=True,
			page_timeout=30*MS,
			exclude_domains=AD_AND_SPAM_DOMAINS,
			exclude_external_links=self.ingestTask.exclude_external_links,
			wait_until='load',
		)
		
	async def generate_urls(self) -> List[str]:
		"""
		Generate URLs with metadata (title, description) from jsonld or HTML head.
		
		Supports:
		- Static URL list
		- URL seeding (CommonCrawl + Sitemap + Queries)
		- URL generation via patterns
		"""
		urls_config = self.ingestTask.urls
		result = []
		seen_urls = set()
		if isinstance(urls_config, list):
			for url in urls_config:
				url_str = str(url)
				if url_str not in seen_urls:
					result.append(url_str)
					seen_urls.add(url_str)

		elif isinstance(urls_config, SeedingURLModel):
			all_urls = await self._generate_from_seeding()
			if urls_config.jsonld != None:
				for url in all_urls:
					jsonld = url.get('json_ld',[])
					if not jsonld:
						continue
					if urls_config.jsonld.match(jsonld):
						result.append(url['url'])	

		elif isinstance(urls_config, URLGeneratorModel):
			async with aiohttp.ClientSession(url) as session:
				for url in generate_urls(urls_config):
					if urls_config.jsonld:
						jsonld = await fetch_jsonld(session,url)
						if not urls_config.jsonld.match(jsonld):
							continue
					result.append(url)
		
		if not result:
			raise NoURLToCrawlError('No valid URLs to crawl after generation and filtering')
		
		return result

	async def build_strategy(self):
		"""Build extraction strategy based on configuration."""
		config = self.ingestTask.extraction
		markdown_generator = DefaultMarkdownGenerator(
			content_filter=PruningContentFilter(),
			options={
			}
		)
		if self.schema:
			schema=self.schema.model_json_schema()
			
		extraction_type='schema'
		apply_chunking=False

		if isinstance(config, TextsExtractionConfig):
			instruction = crawl_prompt.SEMANTIC_TEXT_EXTRACTION_PROMPT_TEMPLATE(
				focus=config.focus,
				persona=config.persona,
				special_instructions=config.instruction,
			)
			apply_chunking=True
			schema = CrawlTextModel.model_json_schema(),
			extraction_type = 'block'

		elif isinstance(config, SchemaExtractionConfig):
			if config.strategy == 'json':
				async with aiohttp.ClientSession() as session:
					strategy = await self.fetch_schema(session)
					return markdown_generator,strategy

			instruction = crawl_prompt.SCHEMA_EXTRACTION_PROMPT(
				target_format='JSON',
				persona=config.persona,
				focus=config.focus,
				special_instructions=config.instruction
			)
			
		elif isinstance(config, KnowledgeGraphExtractionConfig):

			return markdown_generator,None
		
		strategy = LLMExtractionStrategy(
			llm_config=self.llm_config,
			instruction=instruction,
			extraction_type=extraction_type,
			schema=schema,
			apply_chunking=apply_chunking,
			input_format='fit_markdown',
			force_json_response=True,
			overlap_rate=0.2
		)	

		return markdown_generator,strategy

	async def fetch_schema(self,session: aiohttp.ClientSession) -> ExtractionStrategy:
		"""Get cached schema or generate new one."""
		config = self.ingestTask.extraction

		if not config.schema_name or not config.schema_url:
			raise Crawl4AIModeConfigMissingError("schema_name and schema_url required for json_css/regex strategies")
		
		# Check cache
		schema_path = self.schema_dir / f"{config.schema_name}_{config.strategy}.json"
		raw_schema = None
		if schema_path.exists():
			with open(schema_path, 'r') as f:
				raw_schema = json.load(f)
			
		instruction = self.ingestTask.extraction.instruction

		if not raw_schema:
			# Generate new schema
			async with session.get(config.schema_url, timeout=10) as response:
				if response.status == 404:
					raise SchemaHTMLExampleNotFoundError(config.schema_name,config.schema_url,"Page does not exist")
				if response.status == 204:
					raise SchemaHasNoContentError(config.schema_name,config.schema_url,'Page has no content')
				if response.status != 200:
					SchemaFetchError(response.status,config.schema_name,config.schema_url,response.reason)

				html= await response.text()
				try:
					body = BeautifulSoup(html).find('body')
					schema_html = body.text
				except :
					raise SchemaHTMLFormatError(config.schema_name,config.schema_url)

			if not schema_html:
				raise NoInputHtmlSchemaError(config.schema_name,config.schema_url)

			instruction = crawl_prompt.CRAWL4AI_GENERATION_PROMPT(
				schema=self.schema.model_json_schema(),
				persona=config.persona,
				focus=config.focus,
				special_instructions=config.instruction
			)

			match config.strategy:
				case 'json':
					raw_schema = await JsonCssExtractionStrategy.agenerate_schema(
						html=schema_html,
						llm_config=self.llm_config,
						query=instruction,
						usage=self.schema_tokenUsage,
						target_json_example= None
					)	
				case 'regex':
					raw_schema = await RunAsync(RegexExtractionStrategy.generate_pattern)(
						label=...,
						html=schema_html,
						query=instruction,
						llm_config=self.llm_config,
						usage=self.schema_tokenUsage
					)
				case _:
					raise BadSchemaGenerationStrategyError(config.strategy)
		
		if not raw_schema:
			raise SchemaCouldNotBeGeneratedError(config.schema_name,config.schema_url,config.strategy)

		if config.strategy == 'regex':
			strategy = RegexExtractionStrategy(custom=raw_schema)  
		else: 
			strategy = JsonCssExtractionStrategy(raw_schema)
		
		with open(schema_path, 'w') as f:
			json.dump(raw_schema, f, indent=2)
		
		return strategy
			
	async def crawl(self):
		"""
		Main crawl method: generate URLs, extract content, split into chunks.
		"""
		# Crawl all URLs
		results: AsyncGenerator[CrawlResult, None] = await self.crawler.arun_many(
			self.urls,
			self.crawl_config,
		)

		pdf_links = []

		async for result in results:
			metadata = await self.process_result(pdf_links,result,'html')
			if metadata:
				yield metadata
		
		if not pdf_links:
			return 

		pdf_links = list(set(pdf_links))

		pdf_crawler_strategy = PDFCrawlerStrategy()
		pdf_scraping_strategy = PDFContentScrapingStrategy()
		self.crawl_config.scraping_strategy = pdf_scraping_strategy
		self.crawler.crawler_strategy = pdf_crawler_strategy

		results = await self.crawler.arun_many(
			pdf_links,
			self.crawl_config
		)

		async for result in results:
			metadata = await self.process_result(None,result,'pdf')
			if metadata:
				yield metadata
	
	async def start(self):
		"""Start the crawler."""
		await self.crawler.start()

	async def close(self):
		"""Close the crawler and cleanup."""
		await self.crawler.close()

	async def shutdown_deep_crawl(self):
		"""Shutdown deep crawl strategy."""
		if self.deep_crawl_strategy:
			await self.deep_crawl_strategy.shutdown()

	def token_usage(self) -> CrawlTokenUsageReport:
		"""Get total aggregated token usage."""
		usages = []
		
		if self.schema_tokenUsage:
			usage = CrawlTokenUsage(
					step='schema_generation',
					input_tokens=self.schema_tokenUsage.prompt_tokens,
					output_tokens=self.schema_tokenUsage.completion_tokens,
				)
			usages.append(usage)

		if self.strategy and isinstance(self.strategy, LLMExtractionStrategy) and self.strategy.usages:
			for i,usage in enumerate(self.strategy.usages):
				usage: TokenUsage
				usage = CrawlTokenUsage(
						step=f'extraction_{i}',
						input_tokens=usage.prompt_tokens,
						output_tokens=usage.completion_tokens,
					)
				usages.append(usage)
		
		return CrawlTokenUsageReport(
			model=self.crawlLlmConfig._model,
			provider=self.crawlLlmConfig.provider,
			tokens=usages,
			provider_id=self.crawlLlmConfig.provider_id
		)

	async def process_result(self,pdf_links:list[str] | None,result:CrawlResult,doctype:DocType) -> CrawlResultMetadata:
		url = result.url
		metadata = CrawlResultMetadata(url=url, success=result.success, doc_type=doctype)

		if not result.success:
			metadata.error = result.error_message or "Unknown error"
			return metadata
		try:
			url_data = urlparse(url)
			metadata.title = result.metadata.get('title', url)
			metadata.description = result.metadata.get('description', "")
			metadata.source = f"{url_data.scheme}://{url_data.netloc}"

			await self.process_content(result, metadata,doctype)

			if pdf_links is not None and self.ingestTask.pdf and result.links:
				internal_links = result.links.get("internal", [])
				external_links = result.links.get("external", [])

				for link in (internal_links+external_links):
					link:str = link.get('href',None)
					if doctype == 'pdf' and link and link.endswith(f'.{doctype}'):
						pdf_links.append(link['href'])
					elif doctype == 'html' and link and not link.endswith(f'.pdf'):
						pdf_links.append(link['href'])
					else:
						...

			return metadata
		except Exception as e:
			metadata.error = str(e)
			metadata.success = False
			return metadata

	async def process_content(self, result: CrawlResult, metadata: CrawlResultMetadata,doctype:DocType):
		"""Process extracted content based on extraction mode."""
		extraction_config = self.ingestTask.extraction

		if not result.markdown or not hasattr(result.markdown,'fit_markdown') or not result.markdown.fit_markdown:
			metadata.success = False
			metadata.error = result.error_message or "No markdown content extracted"
			return 

		markdown = result.markdown.fit_markdown
		markdown,size = self.slice_markdown(markdown,doctype)  # Example slicing to fit token limits
		
		if isinstance(extraction_config, TextsExtractionConfig): 
			semanticsTexts = result.extracted_content
			semanticsTexts = json.loads(semanticsTexts)

			if not semanticsTexts:
				return
			
			model = CrawlTextModel.model_validate(**semanticsTexts)
			for i,chunk in enumerate(model.texts):
				node_id = f""
				detector = TextDetector(chunk.text)
				stats  = await detector.analyze()
				chunk_meta = chunk.model_dump(exclude=('id',))
				chunk = Chunk(chunk_id=node_id,
							lang=self.ingestTask.lang,
							payload=ChunkPayload(
								document_id=metadata.url,
								document_name=metadata.title or metadata.url,
								document_type="webpage",
								page=0,
								bbox=None,
								**chunk_meta,
								**stats,
								node_id=node_id,
								chunk_index=i,
								extension="md",
								strategy='LLM Text Extraction',
								parser="crawl4ai",
								language=self.ingestTask.lang,
								source=metadata.source,
								category=...,
							))
				metadata.chunks.append(chunk)

		elif isinstance(extraction_config, SchemaExtractionConfig):
			schema_content = result.extracted_content
			if not schema_content:
				return
			metadata.extracted_content = []
			try:
				schema_content = json.loads(schema_content)
			except:
				metadata.success = False
				metadata.error = "Could not process extract the schema"
				return 

			for item in schema_content:
				try:
					item = CrawlSchemaModel.model_validate(item)
					self.schema.model_validate(item.content)
					metadata.extracted_content.append(item)
				except:
					continue

		elif isinstance(extraction_config, KnowledgeGraphExtractionConfig):
			metadata.markdown_content = markdown
			extraction_config.instruction = graphiti_prompt.KG_EXTRACTION_PROMPT(
				extraction_config.persona,
				extraction_config.focus,
				extraction_config.instruction
			)

		self.documents.append(
			MarkdownDocumentSize(
				size=size,
				description=f"Markdown size of {metadata.url} with title {metadata.title} from a {doctype} source",
				doc_type=doctype,
				)
			)

	def _build_deepCrawl_strategy(self):
		"""Build deep crawl strategy with scorers and filters."""
		if not self.ingestTask.deep_crawling:
			return
		
		async def should_cancel():
			return self.crawlState.get('cancelled', False)
		
		model = self.ingestTask.deep_crawling
		Strategy = DEEP_CRAWL_MAP[model.algorithm]
		extra_args = {}
		
		if model.algorithm in ('bfs', 'dfs'):
			extra_args['score_threshold'] = model.score_threshold
		
		# Build scorers
		scorers = _build_scorers(model)
		url_scorer = CompositeScorer(scorers=scorers) if scorers else None
		
		# Build filters
		filter_chain = _build_filters(model)
		
		self.deep_crawl_strategy = Strategy(
			max_depth=model.max_depth,
			max_pages=model.max_pages,
			url_scorer=url_scorer,
			filter_chain=filter_chain,
			resume_state=self.crawlState.get('deep_crawl',None),
			on_state_change=self.dc_state_callback,
			should_cancel=should_cancel,
			include_external_links=model.include_external,
			**extra_args
		)
	
	async def _generate_from_seeding(self):
		seeding_config = self.ingestTask.urls
		seeder = AsyncUrlSeeder()
		all_urls = []
		seen = set()
					
		for q in seeding_config.queries:
			config = SeedingConfig(
				**seeding_config.model_dump(exclude=('domain','queries','speed','top')),
				extract_head=True,
				live_check=True,
				query=q if q else None,
				force=True,
			)
			fetched_urls = await seeder.many_urls(
								seeding_config.domain,
								config
								)
			for _, urls in fetched_urls.items():
				for url in urls:
					if url.get('status','unknown') != 'valid':
						continue
					if url['url'] in seen:
						continue
					seen.add(url['url'])
					all_urls.append(url)

		await seeder.close()      
		all_urls.sort(key=lambda x: x.get('relevance_score',0), reverse=True)

		if seeding_config.top != None:
			all_urls = all_urls[:seeding_config.top]
					
		return all_urls

	def slice_markdown(self, markdown: str, doctype: DocType) -> str:
		"""
		Slice markdown to a maximum size based on doctype.
		Intelligently truncates at paragraph and sentence boundaries to avoid cutting mid-content.
		
		Args:
			markdown: The markdown string to process
			doctype: Either 'html' or 'pdf' to determine max size limit
			
		Returns:
			Markdown string truncated to byte limit, or original if within limit
		"""
		# Get max size in MB based on doctype and convert to bytes
		max_bytes = self.max_markdown_def.get('max_html_mb' if doctype == 'html' else 'max_pdf_mb', 10)
		
		# Check if already within size
		markdown_bytes = markdown.encode('utf-8')
		if len(markdown_bytes) <= max_bytes:
			return markdown
		
		# Split into paragraphs (separated by blank lines)
		paragraphs = markdown.split('\n\n')
		result_parts = []
		current_size = 0
		
		for para_idx, para in enumerate(paragraphs):
			para_bytes = para.encode('utf-8')
			# Account for paragraph separator (\n\n) except for first paragraph
			separator_bytes = len('\n\n'.encode('utf-8')) if para_idx > 0 else 0
			total_para_bytes = len(para_bytes) + separator_bytes
			
			# If adding complete paragraph would exceed limit, try sentence-by-sentence
			if current_size + total_para_bytes > max_bytes:
				# Split paragraph into sentences (periods, question marks, exclamation marks)
				sentences = re.split(r'(?<=[.!?])\s+', para)
				
				for sent_idx, sentence in enumerate(sentences):
					sent_bytes = sentence.encode('utf-8')
					# Add space after sentence if not the last one
					space_bytes = len(' '.encode('utf-8')) if sent_idx < len(sentences) - 1 else 0
					total_sent_bytes = len(sent_bytes) + space_bytes
					
					if current_size + total_sent_bytes <= max_bytes:
						result_parts.append(sentence)
						current_size += total_sent_bytes
					else:
						# Reached size limit, stop processing
						break
				
				# Stop processing more paragraphs
				break
			else:
				# Paragraph fits, add it completely
				result_parts.append(para)
				current_size += total_para_bytes
		
		# Join results
		if not result_parts:
			# Fallback: return truncated string at byte boundary
			return markdown_bytes[:max_bytes].decode('utf-8', errors='ignore')
		
		# Join paragraphs with double newline, sentences with space
		result = '\n\n'.join(result_parts)
		# Ensure we're not exceeding the limit (due to encoding edge cases)
		while len(result.encode('utf-8')) > max_bytes and result:
			# Remove last sentence/character if still over
			result = result.rsplit(' ', 1)[0] if ' ' in result else result[:-1]
		
		return result,current_size

def _build_scorers(self, model: DeepCrawlingStrategyModel) -> List:
	"""Build list of scorers from model."""
	scorers = []
	
	if not model.url_scorers:
		return scorers
	
	for scorer_model in model.url_scorers:
		if scorer_model.mode == 'keyword':
			scorers.append(KeywordRelevanceScorer(
				keywords=scorer_model.keyword,
				weight=scorer_model.weight
			))
		elif scorer_model.mode == 'domain_authority':
			scorers.append(DomainAuthorityScorer(
				domain_weights=scorer_model.domain_weights,
				default_weight=scorer_model.default_weight or 0.5,
				weight=scorer_model.weight
			))
		elif scorer_model.mode == 'path_depth':
			scorers.append(PathDepthScorer(weight=scorer_model.weight))
		elif scorer_model.mode == 'content_type':
			scorers.append(ContentTypeScorer(
				type_weights=scorer_model.type_weights,
				weight=scorer_model.weight
			))
		elif scorer_model.mode == 'freshness':
			scorers.append(FreshnessScorer(
				current_year=scorer_model.current_year,
				weight=scorer_model.weight
			))
	
	return scorers

def _build_filters(self, model: DeepCrawlingStrategyModel) -> Optional[FilterChain]:
	"""Build filter chain from model."""
	if not model.url_filters:
		return None
	
	filters = []
	
	for filter_model in model.url_filters:
		if filter_model.mode == 'url_pattern':
			filters.append(URLPatternFilter(
				patterns=filter_model.patterns,
				threshold=filter_model.threshold
			))
		elif filter_model.mode == 'domain':
			filters.append(DomainFilter(
				include_domains=filter_model.include_domains,
				blocked_domains=filter_model.blocked_domains,
			))
		elif filter_model.mode == 'content_type':
			filters.append(ContentTypeFilter(
				allowed_types=filter_model.allowed_types,
			))
		elif filter_model.mode == 'content_relevance':
			filters.append(ContentRelevanceFilter(
				query=filter_model.query,
				similarity_threshold=filter_model.similarity_threshold or 0.5,
				threshold=filter_model.threshold
			))
		elif filter_model.mode == 'seo':
			filters.append(SEOFilter(
				threshold=filter_model.threshold,
				keywords=filter_model.keywords
			))
	
	return FilterChain(filters) if filters else None
