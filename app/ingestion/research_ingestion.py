from aiohttp_retry import Callable

from app.classes.crawl import DigestState
from app.models.ingest_model import ResearchDataIngestModel
from enum import Enum
from .crawl_ingestion import WebCrawlerIngestion
from crawl4ai import  AdaptiveCrawler,AdaptiveConfig,LLMConfig
from typing import Awaitable, List

class ResearchIngestionStepIndex(int, Enum):
    CHECK = 1
    TOKEN_VERIFY = 2
    QUERY_LOOKUP = 3
    LINKS_LOOKUP = 4
    LOOKUP_COST = 5
    RESEARCH = 6
    RESULT_COST = 7
    CLEANUP = 8

class ResearchIngestion(WebCrawlerIngestion):

    def __init__(self,
                researchTask:ResearchDataIngestModel,
                crawl_llm_config,
                extra_headers = None,
                digest_callback:Callable[[DigestState], Awaitable[None]]|None = None,
                base_dir = None,
                ):
        
        self.researchTask = researchTask
        self.digest_callback = digest_callback

        self.create_research_config()
        super().__init__(None, crawl_llm_config,None, extra_headers, None, base_dir, ...)

    def create_research_config(self):
        ... 

    async def research(self):
        digest_provider = f"{self.digest_provider}/{self.digest_embedding_model.model}"
        
        adaptive = AdaptiveCrawler(
            self.crawler,
            config = AdaptiveConfig(
                embedding_llm_config=LLMConfig(
                    provider=digest_provider,
                    api_token=self.digest_api_token,
                    **self.digest_embedding_model.model_dump(exclude=('model',))
                ),
                **self.ingestTask.digest_config.config.model_dump()
                )
            )

        for q in self.ingestTask.digest_config.query:
            state = await adaptive.digest(
                start_url=self,
                query=q
            )

    async def expand_query(self,query:str)->List[str]:
        ...

    
    
