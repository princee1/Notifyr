import json

from aiohttp_retry import Callable
from pydantic import BaseModel, ValidationError
from app.classes.crawl import CrawlLLMConfig, DigestState
from app.models.crawal4ai_model import PDFLinkPreviewModel, SchemaExtractionConfig
from app.models.ingest_model import ResearchDataIngestModel, WebCrawlingDataIngestModel
from enum import Enum
from app.prompt import research_prompt
from .crawl_ingestion import WebCrawlerIngestion
from crawl4ai import  AdaptiveCrawler,AdaptiveConfig,LLMConfig
from typing import Awaitable, Dict, List
from litellm import ModelResponse, acompletion
from app.classes.research import EXAMPLE_SCHEMA_NAME, QueryExpansionModel, search_example_url, search_query_creator,SearchLinkResultModel,SearchEngine

class ResearchIngestionStepIndex(int, Enum):
    CHECK = 1
    TOKEN_VERIFY = 2
    QUERY_EXPANSION = 3
    LINKS_LOOKUP = 4
    LOOKUP_COST = 5
    RESEARCH = 6
    RESULT_COST = 7
    CLEANUP = 8

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

        self.concepts:List[str] = []
        self.research_urls:Dict[str,str] = {}

        super().__init__(None, crawl_llm_config,None, extra_headers, None, base_dir, SearchLinkResultModel)

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

    async def research(self):
        adaptive = AdaptiveCrawler(
            self.crawler,
            config = AdaptiveConfig(
                embedding_llm_config=LLMConfig(
                    provider=self.digest_llm_config.formatted_provider(),
                    api_token=self.digest_llm_config.api_token,
                    **self.digest_llm_config.model.model_dump(exclude={'model'})                                                             
                ),
                **self.researchTask.config.model_dump()
                )
            )

        for urls,query in self.research_urls.items():
            state = await adaptive.digest(
                start_url=urls,
                query=query
            )

            yield {}

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