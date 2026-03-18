from dataclasses import dataclass
from typing import Any, AsyncGenerator, Callable, Dict, List, Literal, Optional, Type, TypedDict
import aiohttp
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlResult, CrawlStrategy, CrawlerRunConfig, CacheMode, AdaptiveCrawler,AdaptiveConfig
from crawl4ai import LLMConfig, LLMExtractionStrategy, JsonCssExtractionStrategy, PruningContentFilter,LLMContentFilter
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy, DFSDeepCrawlStrategy,BestFirstCrawlingStrategy,DeepCrawlStrategy
from crawl4ai import AsyncUrlSeeder, SeedingConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer,DomainAuthorityScorer,PathDepthScorer,ContentTypeScorer,CompositeScorer,FreshnessScorer
from crawl4ai.deep_crawling.filters import URLPatternFilter, DomainFilter, ContentTypeFilter, ContentRelevanceFilter, SEOFilter,FilterChain

from app.classes.crawl import fetch_jsonld, generate_urls
from app.definition._error import BaseError
from app.models.crawal4ai_model import DeepCrawlingAlgorithm, SeedingURLModel, URLGeneratorModel
from app.models.ingest_model import WebCrawlingDataIngestModel, DeepCrawlingStrategyModel
from app.models.llm_model import CrawlLLMConfig, BaseTemperatureMaxTokenModel, WebResearchConfig
from app.classes.chunk import ChunkPayload,Chunk


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


class CrawlError(TypedDict):
    url:str
    message:str


@dataclass
class LLMGeneralConfig:
    provider:str
    model:CrawlLLMConfig|WebResearchConfig
    api_token:str

    def formatted_provider(self):
        return f"{self.provider}/{self.model.model}"


class WebCrawlerIngestion:
    
    def __init__(self,ingestTask:WebCrawlingDataIngestModel,crawl_llm_config:LLMGeneralConfig,deep_crawl_state:Dict[str|Any]|None,extra_headers:dict=lambda:dict(),dc_state_callback:Callable[[Dict[str, Any]],None]|None=None,base_dir=None):
        self.session_id:str|Callable[[],str] = ...
        self.user_agent:str|Callable[[],str] = ...

        self.dc_state_callback = dc_state_callback
        self.deep_crawl_state = deep_crawl_state
        self.ingestTask = ingestTask
        self.base_dir = base_dir
        self.crawl_llm_config = crawl_llm_config

        self.deepCrawlStrategy = None
        self.urls:dict[str,str] = {}

        self.build_configuration()

    def build_configuration(self):
        llm_config_provider = f"{self.crawl_llm_config.provider}/{self.crawl_llm_config.model.model}"
        self.llm_config = LLMConfig(provider=llm_config_provider,
                                    **self.crawl_llm_config.model.model_dump(exclude=('model',)),
                                    api_token=self.crawl_llm_config.api_token
                                    )
        
        self.crawler = AsyncWebCrawler(
            config=BrowserConfig(
                headless=True,
                use_managed_browser=False,
            ),
            session_id=self.session_id() if callable(self.session_id) else self.session_id,
        )
        
    async def crawl(self,):
        
        self.build_deepCrawl_strategy()
        await self.generate_urls()
        extraction_strategy = self.build_extraction_strategy()

        llm_filter = LLMContentFilter(
            llm_config=self.llm_config,
            instruction="",
            ignore_cache=False
        )

        crawl_config = CrawlerRunConfig(
            stream=True,
            deep_crawl_strategy=self.deepCrawlStrategy,
            extraction_strategy=extraction_strategy,
            exclude_external_images=True,
            wait_for_images=True,
            scan_full_page=True,
            scroll_delay=0.5,
            remove_forms=True,
            js_only=True
        )

        not_succeded_crawl = []

        results:AsyncGenerator[CrawlResult,None] = await self.crawler.arun_many(
            self.urls.keys(),
            crawl_config,
        )
        async for result in results: 
            if not result.success:
                not_succeded_crawl.append(
                    CrawlError(url=result.url,message=result.error_message)
                )
                continue

            if ...:
                ...
                
            else:
                ...

    async def start(self):
        await self.crawler.start()
    
    async def close(self):
        await self.crawler.close()

    async def shutdown_deep_crawl(self):
        if self.deepCrawlStrategy:
            await self.deepCrawlStrategy.shutdown()
        
    async def generate_urls(self):
        
        if isinstance(self.ingestTask.urls, list):
            return self.ingestTask.urls
        
        if isinstance(self.ingestTask.urls,SeedingURLModel):
            seeding_config = self.ingestTask.urls
            seeder = AsyncUrlSeeder()
            
            all_urls = []
            seen = set()
            
            for q in seeding_config.queries:
                extract_head = bool(seeding_config.jsonld) or bool(q)

                config = SeedingConfig(
                    **seeding_config.model_dump(exclude=('domain','queries','speed','top')),
                    extract_head=extract_head,
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

            filtered_url = []

            if seeding_config.jsonld != None:
                for url in all_urls:
                    jsonld = url.get('json_ld',[])
                    if not jsonld:
                        continue
                    matches = []
                    for jsld in jsonld[:5]:
                        m = seeding_config.jsonld.match(jsld)
                        matches.append(m)
                    if any(matches):
                        filtered_url.append(url['url'])
                
                return filtered_url
            else:
                return[ u['url'] for u in all_urls]
        
        if isinstance(self.ingestTask.urls,URLGeneratorModel):
            generator_config = self.ingestTask.urls

            if generator_config.jsonld:
                async with aiohttp.ClientSession(url) as session:
                    for url in generate_urls(generator_config):
                        jsonld = await fetch_jsonld(session,url)
                        matches = []

                        for jsld in jsonld[:5]:
                            m = generator_config.jsonld.match(jsld)
                            matches.append(m)
                        if any(matches):
                            yield url
            else:
                yield generate_urls(generator_config)

        raise ValueError('Bad value for the url')

    def build_deepCrawl_strategy(self):
        
        deep_crawl_model: DeepCrawlingStrategyModel = self.ingestTask.deep_crawling
        
        if not deep_crawl_model:
            return
        
        extra_args = {}
        Strategy = DEEP_CRAWL_MAP[deep_crawl_model.algorithm]

        if deep_crawl_model.algorithm in ('bfs', 'dfs'):
            extra_args['score_threshold'] = deep_crawl_model.score_threshold

        self.deepCrawlStrategy  = Strategy(
            max_depth=deep_crawl_model.max_depth,
            max_pages=deep_crawl_model.max_pages,
            url_scorer=_build_scorer(),
            filter_chain=_build_filters(),
            resume_state=self.deep_crawl_state,
            on_state_change=self.dc_state_callback,
            include_external_links=deep_crawl_model.include_external,
            **extra_args
        )

        return 

    def build_extraction_strategy(self):
        ...
    
        
def _build_filters(deepCrawlModel:DeepCrawlingStrategyModel):
    if not deepCrawlModel.url_filters:
        return None
    
    filters = []
    for filter_model in deepCrawlModel.url_filters:
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

def _build_scorer(deepCrawlModel:DeepCrawlingStrategyModel):
    scorers = []

    if deepCrawlModel.url_scorers:
        for scorer_model in deepCrawlModel.url_scorers:
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

        
                    