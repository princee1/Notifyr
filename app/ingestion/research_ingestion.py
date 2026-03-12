from .crawl_ingestion import WebCrawlerIngestion
from crawl4ai import  AdaptiveCrawler,AdaptiveConfig,LLMConfig

research_site= [
    'google.com'
]

class ResearchIngestion(WebCrawlerIngestion):
    ...

    async def digest(self):
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
    

    async def research(self):
        ...
