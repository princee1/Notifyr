from typing import Any, Callable, Dict
from crawl4ai import AsyncWebCrawler, BrowserConfig,CrawlerRunConfig
from crawl4ai import LLMConfig,LLMTableExtraction,LLMExtractionStrategy,LLMContentFilter, JsonCssExtractionStrategy
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy, DFSDeepCrawlStrategy,BestFirstCrawlingStrategy
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from app.models.ingest_model import DataIngestWebCrawlingModel

class WebCrawlerIngestion:
    
    def __init__(self,ingestTask:DataIngestWebCrawlingModel,provider:str,api_token:str,extra_headers:dict=lambda:dict(),state_callback:Callable[[Dict[str, Any]],None]=lambda:...,base_dir=None):
        self.session_id:str = ...
        self.user_agent:str = ...
        self.provider = provider
        self.api_token = api_token
        self.state_callback = state_callback
        self.ingestTask = ingestTask
        self.base_dir = base_dir

        self._build_configuration()

    def _build_configuration(self):
        llm_config = LLMConfig()
        crawl_config = CrawlerRunConfig(
            deep_crawl_strategy=...,
            extraction_strategy=...,
            markdown_generator=...,
            
        )

        self.crawler = AsyncWebCrawler(
            config=BrowserConfig(

            )
        )

    async def crawl(self,):


        await self.crawler.arun_many(

        )

    async def digest(self):
        ...
    
    async def start(self):
        await self.crawler.start()
    
    async def close(self):
        await self.crawler.close()