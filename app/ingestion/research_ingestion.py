import asyncio
import json
from pathlib import Path
import sys
from typing_extensions import Literal

from aiohttp_retry import Callable
from pydantic import BaseModel, ValidationError
from app.classes.cost_definition import MarkdownCostDefinition
from app.classes.crawl import CrawlLLMConfig, CrawlTokenUsageReport, DigestState, MarkdownDocumentSize
from app.models.crawal4ai_model import PDFLinkPreviewModel, SchemaExtractionConfig
from app.models.ingest_model import ResearchDataIngestModel, WebCrawlingDataIngestModel
from enum import Enum
from app.prompt import research_prompt
from app.utils.constant import Crawl4AIConstant
from .crawl_ingestion import WebCrawlerIngestion
from crawl4ai import  AdaptiveCrawler,AdaptiveConfig, CrawlResult, CrawlState,LLMConfig
from typing import Awaitable, Dict, List
from litellm import ModelResponse, Usage, acompletion
from app.classes.research import EXAMPLE_SCHEMA_NAME, QueryExpansionModel, ResearchDocument, ResearchResultMetadata, SearchLinkState, extract_query, search_example_url, search_query_creator,SearchLinkResultModel,SearchEngine

class ResearchIngestionStepIndex(int, Enum):
    QUERY_EXPANSION = 1
    QUERY_COST = 2
    LINKS_LOOKUP = 3
    LOOKUP_COST = 4
    FILTER_URL = 5
    RESEARCH = 6
    RESULT_COST = 7
    CLEANUP = 8

class ResearchIngestion(WebCrawlerIngestion):

    def __init__(self,
                researchTask:ResearchDataIngestModel,
                crawl_llm_config:CrawlLLMConfig,
                digest_llm_config:CrawlLLMConfig,
                markdownResearch:MarkdownCostDefinition,
                state:dict,
                extra_headers = None,
                base_dir = None,
                ):
        
        self.digest_llm_config = digest_llm_config
        self.researchTask = researchTask
        self.research_state = state
        self.research_dir = Path(base_dir) / Crawl4AIConstant.RESEARCH_CACHE_DIR / f'{self.researchTask.name.strip('.research')}'
        self.research_dir.mkdir(exist_ok=True)

        super().__init__(None, crawl_llm_config,markdownResearch, extra_headers, None, base_dir, SearchLinkResultModel)

    def clear_cost(self):
        self.documents = []
    
    def process_research_content(self,doc:ResearchDocument,results:dict[str,CrawlResult])->ResearchResultMetadata:
        result = results.get(doc['url'],None)
        if not result:
            return ResearchResultMetadata(None,None,None,None,f'{doc["url"]} result not found',False)
        
        if not result.success:
            return ResearchResultMetadata(None,None,None,None,result.error_message,False)

        markdown,size = self.slice_markdown(doc.get('content'),'html')
        self.documents.append(
            MarkdownDocumentSize(
                size=size,
                description=f'Summary research of {doc["url"]}',
                doc_type='html'
                )
        )
        title = result.metadata.get('title', doc['url'])
        description = result.metadata.get('description', "")
        return ResearchResultMetadata(
            markdown=markdown,
            source=doc['url'],
            description=description,
            title=title,
            success=True,
            error_message=None
        )

    async def filter_urls(self,urls:dict[str,SearchLinkState]):
        results = []
        for url,state in urls.items():
            query = state['query']
            content = SearchLinkResultModel(**state['content'])
            ...

            results.append([url,query])
        
        return results
        
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
                    view_urls.add(urls)
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

    async def research(self,urls:list[tuple[str,str]]):

        cache_path = self.compute_path('cache','str')
        kb_path = self.compute_path('kb','path')

        adaptive = AdaptiveCrawler(
            self.crawler,
            config = AdaptiveConfig(
                save_state=True,
                save_path=cache_path,
                embedding_llm_config=LLMConfig(
                    provider=self.digest_llm_config.formatted_provider(),
                    api_token=self.digest_llm_config.api_token,
                    **self.digest_llm_config.model.model_dump(exclude={'model'})                                                             
                ),
                **self.researchTask.config.model_dump()
                )
            )
        if kb_path.exists():
            adaptive.import_knowledge_base(kb_path)
            #NOTE Lookup the difference between knowledge base and 
        try:
            for url,query in urls:
                    state = await adaptive.digest(
                        start_url=url,
                        query=query,
                        resume_from=cache_path,
                    )   
        except (asyncio.CancelledError,Exception) as e:
            adaptive.export_knowledge_base(kb_path)
            raise e from e
        
        state = state or adaptive.state

        if not state:
            ...
        
        results = {}
        for r in state.knowledge_base:
            results[r.url] = r

        for doc in adaptive.get_relevant_content(top_k=self.researchTask.top_k):
                yield self.process_research_content(doc,results)

    async def query_expansion(self)->List[str]:
        try:
            query = self.researchTask.query
            response:ModelResponse = await acompletion(
                model=self.crawlLlmConfig.model.model,
                messages=[{"role": "system", "content": research_prompt.QUERY_EXPANSION_SYSTEM_MESSAGE},
                          {"role": "user", "content": research_prompt.QUERY_EXPANSION_PROMPT(query)}],
                api_key=self.crawlLlmConfig.api_token,
                max_completion_tokens=self.crawlLlmConfig.model.max_tokens,
                reasoning_effort='medium',
                stream=False,
            )
            #usage = response.usage or Usage()
            choices = response.choices
            if not choices:
                raise 
            content = choices[0].message.content
            parsed = json.loads(content)
            return QueryExpansionModel(concepts=parsed).concepts
            
        except (json.JSONDecodeError, ValidationError):
            return [query]
        
    def compute_path(self,file:Literal['cache','kb'],mode:Literal['str','path']):
        file = 'cache.json' if file == 'cache' else 'kb.jsonl'
        path = (self.research_dir / file)
        if mode == 'path':
            return path
        
        path = path.absolute()
        return path.as_uri().split('file:///')[1]