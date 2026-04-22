import json
from pathlib import Path

from aiohttp_retry import Callable
from pydantic import BaseModel, ValidationError
from app.classes.crawl import CrawlLLMConfig, DigestState
from app.models.crawal4ai_model import PDFLinkPreviewModel, SchemaExtractionConfig
from app.models.ingest_model import ResearchDataIngestModel, WebCrawlingDataIngestModel
from enum import Enum
from app.prompt import research_prompt
from app.utils.constant import Crawl4AIConstant
from .crawl_ingestion import WebCrawlerIngestion
from crawl4ai import  AdaptiveCrawler,AdaptiveConfig,LLMConfig
from typing import Awaitable, Dict, List
from litellm import ModelResponse, acompletion
from app.classes.research import EXAMPLE_SCHEMA_NAME, QueryExpansionModel, ResearchResultMetadata, SearchLinkState, extract_query, search_example_url, search_query_creator,SearchLinkResultModel,SearchEngine

class ResearchIngestionStepIndex(int, Enum):
    QUERY_EXPANSION = 1
    LINKS_LOOKUP = 2
    LOOKUP_COST = 3
    RESEARCH = 4
    RESULT_COST = 5
    CLEANUP = 6

class ResearchIngestion(WebCrawlerIngestion):

    def __init__(self,
                researchTask:ResearchDataIngestModel,
                crawl_llm_config:CrawlLLMConfig,
                digest_llm_config:CrawlLLMConfig,
                state:dict,
                extra_headers = None,
                digest_callback:Callable[[DigestState], Awaitable[None]]|None = None,
                base_dir = None,
                ):
        
        self.digest_llm_config = digest_llm_config
        self.researchTask = researchTask
        self.digest_callback = digest_callback
        self.research_state = state

        self.research_dir = Path(base_dir) / Crawl4AIConstant.RESEARCH_CACHE_DIR

        super().__init__(None, crawl_llm_config,None, extra_headers, None, base_dir, SearchLinkResultModel)

    def clear_cost(self):
        ...
    
    def process_research_content(self):
        ...

    async def crawl(self)->dict[str,SearchLinkState]:
        view_urls = set()
        urls = {}
        async for result in super().crawl():
            if not result.success:
                continue

            if not result.extracted_content:
                continue
                
            query = extract_query(result.url,self.researchTask.engine)
            
            for item in result.extracted_content:
                url = item.content.get('url',None)
                if url and url not in view_urls:
                    urls[url] = {
                        'query':query,
                        'content':item.content,
                    }
        return urls

    async def set_crawl_task(self,concepts:list[str]):
        url_generator = search_query_creator(concepts)
        schema_url = search_example_url(self.researchTask.engine)
        self.ingestTask = WebCrawlingDataIngestModel(
            extraction=SchemaExtractionConfig(strategy='json',
                                              schema_name=EXAMPLE_SCHEMA_NAME,
                                              schema_url=schema_url,
                                              custom_schema=None,
                                              **research_prompt.SEARCH_RESULT_SCHEMA_PROMPT
                                              ),
            urls=url_generator,
            pdf=None,
            name=self.researchTask.name
        )

    async def research(self,urls:dict[str,SearchLinkState]):
        adaptive = AdaptiveCrawler(
            self.crawler,
            config = AdaptiveConfig(
                save_state=True,
                save_path=...,
                embedding_llm_config=LLMConfig(
                    provider=self.digest_llm_config.formatted_provider(),
                    api_token=self.digest_llm_config.api_token,
                    **self.digest_llm_config.model.model_dump(exclude={'model'})                                                             
                ),
                **self.researchTask.config.model_dump()
                )
            )
        
        for url,results in urls.items():
            query = results['query']
            content = SearchLinkResultModel(**results['content'])

        for url in []:
            state = await adaptive.digest(
                start_url=url,
                query=query,
                resume_from=...,
            )

            if state.metrics.get('is_irrelevant', False):
                continue
            
        for doc in adaptive.get_relevant_content(top_k=self.researchTask.top_k):
            yield ResearchResultMetadata()

    async def query_expansion(self)->List[str]:
        try:
            query = self.researchTask.query
            response = await acompletion(
                model=self.crawlLlmConfig.model.model,
                messages=[{"role": "system", "content": research_prompt.QUERY_EXPANSION_SYSTEM_MESSAGE},
                          {"role": "user", "content": research_prompt.QUERY_EXPANSION_PROMPT(query)}],
                api_key=self.crawlLlmConfig.api_token,
                stream=False,
            )
            choices = response.choices
            if not choices:
                raise 
            content = choices[0].message.content
            parsed = json.loads(content)
            return QueryExpansionModel(concepts=parsed).concepts
            
        except (json.JSONDecodeError, ValidationError):
            return [query]