from typing import Any, Callable, Dict, List, Literal, Optional, Type
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlStrategy, CrawlerRunConfig, CacheMode, AdaptiveCrawler,AdaptiveConfig
from crawl4ai import LLMConfig, LLMExtractionStrategy, JsonCssExtractionStrategy, PruningContentFilter
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy, DFSDeepCrawlStrategy,BestFirstCrawlingStrategy,DeepCrawlStrategy
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai import AsyncUrlSeeder, SeedingConfig
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer,DomainAuthorityScorer,PathDepthScorer,ContentTypeScorer,CompositeScorer,FreshnessScorer
from crawl4ai.deep_crawling.filters import URLPatternFilter, DomainFilter, ContentTypeFilter, ContentRelevanceFilter, SEOFilter,FilterChain

from app.definition._error import BaseError
from app.models.crawal4ai_model import DeepCrawlingAlgorithm
from app.models.ingest_model import DataIngestWebCrawlingModel, DeepCrawlingStrategyModel
from app.models.llm_model import CrawlLLMConfig, BaseTemperatureMaxTokenModel


class CrawlNotSucceededError(BaseError):
    def __init__(self, url:str):
        super().__init__(url)
        self.url = url

class Crawl4AIModeConfigMissingError(BaseError):
    def __init__(self, config:Literal['crawl','digest']):
        super().__init__(config)
        self.config=config


DEEP_CRAWL_MAP:Dict[DeepCrawlingAlgorithm,Type[DeepCrawlStrategy]] = {
    'bfs':BFSDeepCrawlStrategy,
    'dfs':DFSDeepCrawlStrategy,
    'best-first':BestFirstCrawlingStrategy,
}


class WebCrawlerIngestion:
    
    def __init__(self,ingestTask:DataIngestWebCrawlingModel,crawl_provider:str,llm_model:CrawlLLMConfig,digest_provider:str,digest_model:BaseTemperatureMaxTokenModel,embedding_api_token:str,llm_api_token:str,deep_crawl_state:Dict[str|Any]|None,extra_headers:dict=lambda:dict(),dc_state_callback:Callable[[Dict[str, Any]],None]|None=None,base_dir=None):
        self.session_id:str|Callable[[],str] = ...
        self.user_agent:str|Callable[[],str] = ...
        self.crawl_llm_model = llm_model
        self.crawl_provider = crawl_provider
        self.digest_provider = digest_provider
        self.digest_embedding_model =digest_model
        self.crawl_api_token = llm_api_token
        self.digest_api_token = embedding_api_token
        self.dc_state_callback = dc_state_callback
        self.deep_crawl_state = deep_crawl_state
        self.ingestTask = ingestTask
        self.base_dir = base_dir
        self.deep_crawl_strategy = None

        self.build_configuration()

    def build_configuration(self):
        llm_config_provider = f"{self.crawl_provider}/{self.crawl_llm_model.model}"
        self.llm_config = LLMConfig(provider=llm_config_provider,
                                    **self.crawl_llm_model.model_dump(exclude=('model',)),
                                    api_token=self.crawl_api_token
                                    )
        self.crawler = AsyncWebCrawler(
            config=BrowserConfig(
                headless=True,
                use_managed_browser=False,
            ),
            session_id=self.session_id() if callable(self.session_id) else self.session_id,
        )
        
    async def crawl(self,):
        
        self.deep_crawl_strategy = self._build_deep_crawl_strategy()
        urls = self._build_urls()
        extraction_strategy = self._build_extraction_strategy()
        generation_strategy = self._build_generation_strategy()

        crawl_config = CrawlerRunConfig(
            stream=True,
            deep_crawl_strategy=self.deep_crawl_strategy,
            extraction_strategy=extraction_strategy,
            markdown_generator=generation_strategy, 
            exclude_external_images=True,
            wait_for_images=True,
        )

        results = await self.crawler.arun_many(
            urls,
            crawl_config,

        )

    async def start(self):
        await self.crawler.start()
    
    async def close(self):
        await self.crawler.close()

    async def shutdown_deep_crawl(self):
        if self.deep_crawl_strategy:
            await self.deep_crawl_strategy.shutdown()
        
    def _build_deep_crawl_strategy(self):
        
        deep_crawl_model: DeepCrawlingStrategyModel = self.ingestTask.deep_crawling
        
        if not deep_crawl_model:
            return None
        
        extra_args = {}
        Strategy = DEEP_CRAWL_MAP[deep_crawl_model.algorithm]

        if deep_crawl_model.algorithm in ('bfs', 'dfs'):
            extra_args['score_threshold'] = deep_crawl_model.score_threshold

        def _build_filters():
            if not deep_crawl_model.url_filters:
                return None
            
            filters = []
            
            for filter_model in deep_crawl_model.url_filters:
                match filter_model.mode:
                    case 'url_pattern':
                        filters.append(URLPatternFilter(
                            patterns=filter_model.patterns,
                            threshold=filter_model.threshold
                        ))
                    
                    case 'domain':
                        filters.append(DomainFilter(
                            include_domains=filter_model.include_domains,
                            blocked_domains=filter_model.blocked_domains,
                        ))
                    
                    case 'content_type':
                        filters.append(ContentTypeFilter(
                            allowed_types=filter_model.allowed_types,
                        ))
                    
                    case 'content_relevance':
                        filters.append(ContentRelevanceFilter(
                            query=filter_model.query,
                            similarity_threshold=filter_model.similarity_threshold or 0.5,
                            threshold=filter_model.threshold
                        ))
                    
                    case 'seo':
                        filters.append(SEOFilter(
                            threshold=filter_model.threshold,
                            keywords=filter_model.keywords
                        ))
            
            return FilterChain(filters) if filters else None 

        def _build_scorer():
            scorers = []

            if deep_crawl_model.url_scorers:
                for scorer_model in deep_crawl_model.url_scorers:
                    match scorer_model.mode:
                        case 'keyword':
                            scorers.append(KeywordRelevanceScorer(
                                keywords=scorer_model.keyword,
                                weight=scorer_model.weight
                            ))
                        
                        case 'domain_authority':
                            scorers.append(DomainAuthorityScorer(
                                domain_weights=scorer_model.domain_weights,
                                default_weight=scorer_model.default_weight or 0.5,
                                weight=scorer_model.weight
                            ))
                        
                        case 'path_depth':
                            scorers.append(PathDepthScorer(
                                weight=scorer_model.weight
                            ))
                        
                        case 'content_type':
                            scorers.append(ContentTypeScorer(
                                type_weights=scorer_model.type_weights,
                                weight=scorer_model.weight
                            ))
                        
                        case 'freshness':
                            scorers.append(FreshnessScorer(
                                current_year=scorer_model.current_year,
                                weight=scorer_model.weight
                            ))
            
            return CompositeScorer(scorers=scorers) if scorers else None
        
        return Strategy(
            max_depth=deep_crawl_model.max_depth,
            max_pages=deep_crawl_model.max_pages,
            url_scorer=_build_scorer(),
            filter_chain=_build_filters(),
            resume_state=self.deep_crawl_state,
            on_state_change=self.dc_state_callback,
            include_external_links=deep_crawl_model.include_external,
            **extra_args
        )

    def _build_extraction_strategy(self):
        ...

    def _build_generation_strategy(self):
        ...

    async def _build_urls(self):
        
        if isinstance(self.)
        
        seeder = AsyncUrlSeeder()

        config = SeedingConfig(
            extract_head=True,
            live_check=True,
            hits_per_sec=10,
            force=True,
            pattern=...,
            validate_sitemap_lastmod=True
        )