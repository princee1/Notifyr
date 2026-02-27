from typing import Callable
from crawl4ai import AsyncWebCrawler, BrowserConfig,CrawlerRunConfig
from crawl4ai import LLMConfig,LLMTableExtraction,LLMExtractionStrategy,LLMContentFilter
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy, DFSDeepCrawlStrategy,BestFirstCrawlingStrategy
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

class WebCrawlerIngestion:
    
    def __init__(self,provider:str,api_token:str,extra_headers:dict=lambda:dict(),state_callback:Callable=lambda:...):
        self.session_id:str = ...
        self.user_agent:str = ...
        self.state_callback = state_callback

    def _build_configuration(self):
        ...


    async def crawl(self,):
        ...

    async def digest(self):
        ...
    
    async def start(self):
        ...
    
    async def close(self):
        ...